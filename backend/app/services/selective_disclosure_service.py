from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from app.crypto.merkle import (
    SaltedAttributeMerkleTree,
    hash_leaf,
    verify_merkle_proof,
)
from app.crypto.fingerprint import compute_composite_fingerprint
from app.services.challenge_service import ChallengeService
from app.repositories.credential_repository import CredentialRepository
from app.blockchain.client import blockchain_client
from app.core.exceptions import AppException
from app.db.base import utc_now


class SelectiveDisclosureService:
    """
    Selective disclosure presentation generation and verification service.
    Binds attribute claims to Merkle root proofs, composite fingerprints, and verifier challenges.
    """

    def __init__(self, db: Session):
        self.db = db
        self.cred_repo = CredentialRepository(db)
        self.challenge_svc = ChallengeService(db)

    def generate_presentation(
        self,
        credential_id: str,
        version: int,
        attributes: Dict[str, str],
        salts: Dict[str, str],
        disclosed_keys: List[str],
        document_digest: str,
        metadata_digest: str,
        issuer_id: str,
        challenge_id: Optional[str] = None,
        challenge_nonce: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates a selective disclosure presentation revealing only requested attributes,
        along with their opening salts and Merkle proofs.
        """
        if not disclosed_keys:
            raise AppException(
                message="At least one attribute must be selected for disclosure.",
                error_code="EMPTY_DISCLOSED_KEYS",
                status_code=400,
            )

        # 1. Construct Merkle tree from full attributes and salts
        tree = SaltedAttributeMerkleTree(attributes, salts)

        # 2. Extract proofs only for disclosed keys
        disclosed_claims = []
        for key in disclosed_keys:
            if key not in attributes:
                raise AppException(
                    message=f"Requested claim key '{key}' does not exist in credential attributes.",
                    error_code="CLAIM_NOT_FOUND",
                    status_code=400,
                )
            disclosed_claims.append({
                "key": key,
                "value": str(attributes[key]),
                "salt": tree.salts[key],
                "leaf_hash": tree.leaves[key],
                "proof": tree.get_proof(key),
            })

        # 3. Compute authoritative composite fingerprint
        fingerprint = compute_composite_fingerprint(
            document_digest=document_digest,
            metadata_digest=metadata_digest,
            merkle_root=tree.root,
            issuer_id=issuer_id,
            credential_id=credential_id,
            version=version,
        )

        return {
            "credential_fingerprint": fingerprint,
            "credential_id": credential_id,
            "version": version,
            "issuer_id": issuer_id,
            "merkle_root": tree.root,
            "document_digest": document_digest,
            "metadata_digest": metadata_digest,
            "disclosed_claims": disclosed_claims,
            "challenge_id": challenge_id,
            "challenge_nonce": challenge_nonce,
        }

    def verify_presentation(
        self,
        presentation: Dict[str, Any],
        verifier_session_id: str,
        require_current_version: bool = False,
        verifier_principal: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifies selective disclosure presentation:
        1. Validates and atomically consumes verifier challenge (single-use replay prevention and principal binding).
        2. Verifies individual leaf hashes and Merkle proofs against claimed merkle_root.
        3. Verifies composite fingerprint binding.
        4. Verifies database presence, status, and version recency.
        5. Verifies on-chain issuer accreditation, credential status, and expiration if blockchain is reachable.
        """
        fingerprint = presentation.get("credential_fingerprint")
        credential_id = presentation.get("credential_id")
        version = presentation.get("version")
        merkle_root = presentation.get("merkle_root")
        doc_digest = presentation.get("document_digest")
        meta_digest = presentation.get("metadata_digest")
        issuer_id = presentation.get("issuer_id")
        disclosed_claims = presentation.get("disclosed_claims", [])
        challenge_id = presentation.get("challenge_id")
        challenge_nonce = presentation.get("challenge_nonce")

        if not fingerprint or not merkle_root or not disclosed_claims:
            raise AppException(
                message="Malformed presentation: missing fingerprint, merkle_root, or disclosed claims.",
                error_code="MALFORMED_PRESENTATION",
                status_code=400,
            )

        # Step 1: Challenge validation and atomic consumption (if challenge provided)
        challenge_verified = False
        if challenge_id and challenge_nonce:
            self.challenge_svc.validate_and_consume_challenge(
                challenge_id=challenge_id,
                challenge_nonce=challenge_nonce,
                verifier_session_id=verifier_session_id,
                credential_fingerprint=fingerprint,
                verifier_principal=verifier_principal,
            )
            challenge_verified = True

        # Step 2: Cryptographic Merkle proof verification for each disclosed claim
        verified_claims = {}
        for claim in disclosed_claims:
            key = claim.get("key")
            value = claim.get("value")
            salt = claim.get("salt")
            proof = claim.get("proof", [])

            if not key or value is None or not salt:
                raise AppException(
                    message=f"Malformed claim entry for attribute '{key}'.",
                    error_code="MALFORMED_CLAIM",
                    status_code=400,
                )

            recomputed_leaf = hash_leaf(salt, key, str(value))
            is_proof_valid = verify_merkle_proof(proof, merkle_root, recomputed_leaf)

            if not is_proof_valid:
                raise AppException(
                    message=f"Merkle proof verification failed for claim '{key}'. Value, salt, or proof tampered.",
                    error_code="INVALID_MERKLE_PROOF",
                    status_code=400,
                )

            verified_claims[key] = value

        # Step 3: Verify composite fingerprint consistency if full digests provided
        fingerprint_verified = False
        if doc_digest and meta_digest and issuer_id and credential_id and version:
            expected_fp = compute_composite_fingerprint(
                document_digest=doc_digest,
                metadata_digest=meta_digest,
                merkle_root=merkle_root,
                issuer_id=issuer_id,
                credential_id=credential_id,
                version=int(version),
            )
            if expected_fp.lower() != fingerprint.lower():
                raise AppException(
                    message="Composite fingerprint does not match presentation component parameters.",
                    error_code="FINGERPRINT_MISMATCH",
                    status_code=400,
                )
            fingerprint_verified = True

        # Step 4: Database resolution & Version recency
        version_rec = self.cred_repo.get_version_by_fingerprint(fingerprint)
        parent_cred = None
        if version_rec:
            parent_cred = self.cred_repo.get_by_credential_id(version_rec.credential_id)
        else:
            parent_cred = self.cred_repo.get_by_fingerprint(fingerprint)

        db_valid = False
        is_current_version = False
        db_status = "UNKNOWN"

        if parent_cred:
            db_status = parent_cred.current_status
            db_valid = (db_status == "ACTIVE")
            is_current_version = (parent_cred.current_fingerprint.lower() == fingerprint.lower())

            if require_current_version and not is_current_version:
                raise AppException(
                    message=f"Credential version {version} has been superseded by a newer version.",
                    error_code="CREDENTIAL_SUPERSEDED",
                    status_code=409,
                )

        # Step 5: On-chain authoritative verification (if blockchain reachable)
        is_conn = blockchain_client.is_connected()
        on_chain_res = {
            "is_connected": is_conn,
            "on_chain_valid": False,
            "code": "RPC_DISCONNECTED" if not is_conn else "NOT_VERIFIED",
        }

        if is_conn and doc_digest and meta_digest and merkle_root:
            chain_check = blockchain_client.verify_credential_on_chain(
                fingerprint_hex=fingerprint,
                doc_digest_hex=doc_digest,
                meta_digest_hex=meta_digest,
                merkle_root_hex=merkle_root,
            )
            if chain_check:
                on_chain_res["on_chain_valid"] = chain_check.get("is_valid", False)
                on_chain_res["code"] = chain_check.get("code_name", "UNKNOWN")
                on_chain_res["issuer_active"] = chain_check.get("is_issuer_active", False)

        # Distinguish selective disclosure proof validity from overall credential validity:
        # Merkle proof validity alone DOES NOT equal overall validity!
        overall_valid = (
            bool(verified_claims)
            and (not (challenge_id and challenge_nonce) or challenge_verified)
            and (not parent_cred or db_valid)
            and (not is_conn or on_chain_res["on_chain_valid"])
        )

        return {
            "overall_valid": overall_valid,
            "selective_disclosure_valid": True,
            "disclosed_attributes": verified_claims,
            "challenge_verified": challenge_verified,
            "fingerprint_verified": fingerprint_verified,
            "database_status": db_status,
            "is_current_version": is_current_version,
            "blockchain_verification": on_chain_res,
            "privacy_notice": "Selective disclosure proves authenticity of revealed attributes without exposing unrevealed claims. Note that revealed attributes and identifiers may be linkable by verifiers.",
        }
