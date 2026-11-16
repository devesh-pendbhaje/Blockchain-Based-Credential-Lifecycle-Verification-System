from typing import Dict, List, Optional, Any
import time
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

        if set(attributes) != set(salts) or any(not salt for salt in salts.values()):
            raise AppException("Original salts are required for every attribute.", "MISSING_ORIGINAL_SALTS", 400)
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
        presentation: Any,
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
        Fails closed: overall_valid is True ONLY when all authoritative gates pass.
        """
        if hasattr(presentation, "model_dump"):
            pres_dict = presentation.model_dump()
        elif isinstance(presentation, dict):
            pres_dict = presentation
        else:
            pres_dict = dict(presentation)

        fingerprint = pres_dict.get("credential_fingerprint")
        credential_id = pres_dict.get("credential_id")
        version = pres_dict.get("version")
        merkle_root = pres_dict.get("merkle_root")
        doc_digest = pres_dict.get("document_digest")
        meta_digest = pres_dict.get("metadata_digest")
        issuer_id = pres_dict.get("issuer_id")
        disclosed_claims = pres_dict.get("disclosed_claims", [])
        challenge_id = pres_dict.get("challenge_id")
        challenge_nonce = pres_dict.get("challenge_nonce")

        if not fingerprint or not merkle_root or not disclosed_claims:
            raise AppException(
                message="Malformed presentation: missing fingerprint, merkle_root, or disclosed claims.",
                error_code="MALFORMED_PRESENTATION",
                status_code=400,
            )

        # Step 1: Challenge validation and atomic single-use consumption
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
            if hasattr(claim, "model_dump"):
                c_dict = claim.model_dump()
            elif isinstance(claim, dict):
                c_dict = claim
            else:
                c_dict = dict(claim)

            key = c_dict.get("key")
            value = c_dict.get("value")
            salt = c_dict.get("salt")
            proof = c_dict.get("proof", [])

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

        selective_disclosure_valid = bool(len(verified_claims) > 0)

        # Step 3: Verify composite fingerprint consistency if full digests provided
        fingerprint_verified = False
        if doc_digest and meta_digest and issuer_id and credential_id and version is not None:
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
        db_status = "NOT_FOUND"

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

        # Step 5: On-chain authoritative verification
        is_conn = blockchain_client.is_connected()
        is_contract_ok = blockchain_client.is_contract_ready("credential")
        on_chain_res = {
            "is_connected": is_conn,
            "on_chain_valid": False,
            "code": "RPC_DISCONNECTED" if not is_conn else ("CONTRACT_NOT_READY" if not is_contract_ok else "NOT_VERIFIED"),
            "stored_status": "UNKNOWN",
            "issuer_active": False,
            "expires_at": 0,
            "authoritative_verification_available": False,
        }

        if is_conn and is_contract_ok and doc_digest and meta_digest and merkle_root:
            chain_check = blockchain_client.verify_credential_on_chain(
                fingerprint_hex=fingerprint,
                doc_digest_hex=doc_digest,
                meta_digest_hex=meta_digest,
                merkle_root_hex=merkle_root,
            )
            if chain_check:
                on_chain_res["on_chain_valid"] = bool(chain_check.get("is_valid", False))
                on_chain_res["code"] = chain_check.get("code", "UNKNOWN")
                on_chain_res["stored_status"] = chain_check.get("stored_status", "UNKNOWN")
                on_chain_res["issuer_active"] = bool(chain_check.get("is_issuer_active", False))
                on_chain_res["expires_at"] = int(chain_check.get("expires_at", 0))
                on_chain_res["authoritative_verification_available"] = bool(
                    chain_check.get("code") != "UNAVAILABLE" and chain_check.get("network_ok", True)
                )

        # Check expiration dynamically
        now_ts = int(time.time())
        is_expired = False
        expires_at = on_chain_res.get("expires_at", 0)
        if expires_at and expires_at > 0:
            is_expired = now_ts >= expires_at
        elif version_rec and version_rec.expires_at and version_rec.expires_at > 0:
            is_expired = now_ts >= version_rec.expires_at

        if is_expired:
            on_chain_res["on_chain_valid"] = False
            on_chain_res["code"] = "EXPIRED"

        # FAIL CLOSED: overall_valid strictly requires:
        # 1. Valid Merkle proofs (selective_disclosure_valid)
        # 2. Verified fingerprint binding (fingerprint_verified)
        # 3. Verified verifier challenge (challenge_verified)
        # 4. Known active credential in DB (parent_cred and db_valid)
        # 5. Authoritative on-chain verification valid and active with active issuer
        # 6. Unexpired and un-superseded
        overall_valid = bool(
            selective_disclosure_valid
            and fingerprint_verified
            and challenge_verified
            and parent_cred is not None
            and db_valid
            and is_conn
            and is_contract_ok
            and on_chain_res.get("authoritative_verification_available") is True
            and on_chain_res.get("on_chain_valid", False) is True
            and on_chain_res.get("code") == "VALID"
            and on_chain_res.get("stored_status") == "ACTIVE"
            and on_chain_res.get("issuer_active") is True
            and not is_expired
            and (not require_current_version or is_current_version)
        )

        return {
            "overall_valid": overall_valid,
            "selective_disclosure_valid": selective_disclosure_valid,
            "disclosed_attributes": verified_claims,
            "challenge_verified": challenge_verified,
            "fingerprint_verified": fingerprint_verified,
            "database_status": db_status,
            "is_current_version": is_current_version,
            "blockchain_verification": on_chain_res,
            "privacy_notice": "Selective disclosure proves authenticity of revealed attributes without exposing unrevealed claims. Note that revealed attributes and identifiers may be linkable by verifiers.",
        }
