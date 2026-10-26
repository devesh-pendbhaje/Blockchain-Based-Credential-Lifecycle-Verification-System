import json
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.credential import Credential
from app.models.credential_version import CredentialVersion
from app.repositories.credential_repository import CredentialRepository
from app.repositories.issuer_repository import IssuerRepository
from app.schemas.credential import (
    CredentialCreateRequest,
    CredentialResponse,
    CredentialVersionResponse,
    VerificationResponse,
)
from app.crypto.fingerprint import compute_composite_fingerprint
from app.core.exceptions import (
    EntityNotFoundException,
    EntityConflictException,
    InvalidLifecycleTransitionException,
    AppException,
)
from app.blockchain.client import blockchain_client


from app.core.auth.models import AuthenticatedPrincipal


class CredentialService:
    def __init__(self, db: Session):
        self.db = db
        self.cred_repo = CredentialRepository(db)
        self.issuer_repo = IssuerRepository(db)

    def create_credential(self, req: CredentialCreateRequest) -> CredentialResponse:
        correlation_id = req.idempotency_key or str(uuid.uuid4())

        # 1. Verify Issuer exists in DB
        issuer = self.issuer_repo.get_by_issuer_id(req.issuer_id)
        if not issuer:
            self.cred_repo.record_audit(
                event_type="CREDENTIAL_ISSUANCE_REJECTED",
                entity_type="CREDENTIAL",
                entity_id=req.credential_id,
                outcome="FAILURE",
                correlation_id=correlation_id,
                details_json=json.dumps({"reason": f"Issuer {req.issuer_id} not found"}),
            )
            self.db.commit()
            raise EntityNotFoundException(f"Issuer '{req.issuer_id}' not found.")

        if issuer.status == "REVOKED":
            self.cred_repo.record_audit(
                event_type="CREDENTIAL_ISSUANCE_REJECTED",
                entity_type="CREDENTIAL",
                entity_id=req.credential_id,
                outcome="FAILURE",
                correlation_id=correlation_id,
                details_json=json.dumps({"reason": "Issuer is revoked"}),
            )
            self.db.commit()
            raise AppException(
                message=f"Issuer '{req.issuer_id}' is permanently revoked and cannot issue credentials.",
                error_code="ISSUER_REVOKED",
                status_code=400,
            )

        # 2. Compute authoritative 6-input composite fingerprint
        fingerprint = compute_composite_fingerprint(
            document_digest=req.document_digest,
            metadata_digest=req.metadata_digest,
            merkle_root=req.merkle_root,
            issuer_id=req.issuer_id,
            credential_id=req.credential_id,
            version=req.version,
        )

        # 3. Check idempotency key if provided
        if req.idempotency_key:
            existing_by_key = self.cred_repo.get_version_by_idempotency_key(req.idempotency_key)
            if existing_by_key:
                if (
                    existing_by_key.credential_id == req.credential_id
                    and existing_by_key.version == req.version
                    and existing_by_key.fingerprint == fingerprint
                ):
                    parent_cred = self.cred_repo.get_by_credential_id(existing_by_key.credential_id)
                    return CredentialResponse(
                        credential_id=parent_cred.credential_id,
                        issuer_id=parent_cred.issuer_id,
                        current_version=parent_cred.current_version,
                        current_fingerprint=parent_cred.current_fingerprint,
                        current_status=parent_cred.current_status,
                        issuance_status=existing_by_key.issuance_status,
                        issuance_tx_hash=existing_by_key.issuance_tx_hash,
                        created_at=parent_cred.created_at,
                        updated_at=parent_cred.updated_at,
                    )
                else:
                    raise EntityConflictException(
                        f"Idempotency key '{req.idempotency_key}' has already been used for a different credential issuance request."
                    )

        # 4. Check existing credential
        existing_cred = self.cred_repo.get_by_credential_id(req.credential_id)

        if not existing_cred:
            # Initial issuance must be version 1
            if req.version != 1:
                raise AppException(
                    message=f"Initial credential issuance must be version 1, got {req.version}",
                    error_code="INVALID_VERSION",
                    status_code=400,
                )

            # Ensure fingerprint is globally unique
            existing_fp = self.cred_repo.get_version_by_fingerprint(fingerprint)
            if existing_fp:
                raise EntityConflictException(f"Credential fingerprint '{fingerprint}' already exists.")

            credential = Credential(
                credential_id=req.credential_id,
                issuer_id=req.issuer_id,
                current_version=req.version,
                current_fingerprint=fingerprint,
                current_status="ACTIVE",
            )
            version_rec = CredentialVersion(
                credential_id=req.credential_id,
                version=req.version,
                fingerprint=fingerprint,
                idempotency_key=req.idempotency_key,
                document_digest=req.document_digest,
                metadata_digest=req.metadata_digest,
                merkle_root=req.merkle_root,
                expires_at=req.expires_at,
                issuance_status="PENDING",
            )
            self.cred_repo.create_credential(credential, version_rec)

            self.cred_repo.record_audit(
                event_type="CREDENTIAL_ISSUANCE_REQUESTED",
                entity_type="CREDENTIAL",
                entity_id=req.credential_id,
                outcome="SUCCESS",
                correlation_id=correlation_id,
                details_json=json.dumps({"fingerprint": fingerprint, "version": req.version}),
            )
            self.db.commit()

            # Attempt on-chain anchoring if signer and contract are ready
            if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
                anchor_res = blockchain_client.anchor_credential_fingerprint(
                    credential_id_hex=req.credential_id,
                    doc_digest_hex=req.document_digest,
                    meta_digest_hex=req.metadata_digest,
                    merkle_root_hex=req.merkle_root,
                    version=req.version,
                    expires_at=req.expires_at or 0,
                )
                if anchor_res.get("status") == "CONFIRMED":
                    on_chain_fp = anchor_res.get("fingerprint")
                    on_chain_issuer = anchor_res.get("issuer_id")
                    if on_chain_fp and version_rec.fingerprint != on_chain_fp:
                        version_rec.fingerprint = on_chain_fp
                        credential.current_fingerprint = on_chain_fp
                    if on_chain_issuer and credential.issuer_id.lower() != on_chain_issuer.lower():
                        credential.issuer_id = on_chain_issuer

                    version_rec.issuance_status = "CONFIRMED"
                    version_rec.issuance_tx_hash = anchor_res.get("tx_hash")
                    version_rec.block_number = anchor_res.get("block_number")
                    version_rec.chain_id = blockchain_client.chain_id
                    self.cred_repo.record_audit(
                        event_type="CREDENTIAL_ANCHORED_ON_CHAIN",
                        entity_type="CREDENTIAL",
                        entity_id=req.credential_id,
                        outcome="SUCCESS",
                        correlation_id=correlation_id,
                        details_json=json.dumps({
                            "fingerprint": version_rec.fingerprint,
                            "tx_hash": anchor_res.get("tx_hash"),
                            "block_number": anchor_res.get("block_number"),
                            "chain_id": blockchain_client.chain_id,
                        }),
                    )
                    self.db.commit()
                elif anchor_res.get("status") in ("REVERTED", "FAILED"):
                    version_rec.issuance_status = "FAILED"
                    version_rec.issuance_tx_hash = anchor_res.get("tx_hash")
                    self.cred_repo.record_audit(
                        event_type="CREDENTIAL_ANCHORING_FAILED",
                        entity_type="CREDENTIAL",
                        entity_id=req.credential_id,
                        outcome="FAILURE",
                        correlation_id=correlation_id,
                        details_json=json.dumps({
                            "fingerprint": fingerprint,
                            "error": anchor_res.get("error"),
                            "tx_hash": anchor_res.get("tx_hash"),
                        }),
                    )
                    self.db.commit()

            return CredentialResponse(
                credential_id=credential.credential_id,
                issuer_id=credential.issuer_id,
                current_version=credential.current_version,
                current_fingerprint=credential.current_fingerprint,
                current_status=credential.current_status,
                issuance_status=version_rec.issuance_status,
                issuance_tx_hash=version_rec.issuance_tx_hash,
                created_at=credential.created_at,
                updated_at=credential.updated_at,
            )
        else:
            # Credential already exists
            if req.version == existing_cred.current_version:
                # Idempotent response if exact version exists
                existing_ver = self.cred_repo.get_version_by_number(req.credential_id, req.version)
                if existing_ver and existing_ver.fingerprint == fingerprint:
                    return CredentialResponse(
                        credential_id=existing_cred.credential_id,
                        issuer_id=existing_cred.issuer_id,
                        current_version=existing_cred.current_version,
                        current_fingerprint=existing_cred.current_fingerprint,
                        current_status=existing_cred.current_status,
                        issuance_status=existing_ver.issuance_status,
                        issuance_tx_hash=existing_ver.issuance_tx_hash,
                        created_at=existing_cred.created_at,
                        updated_at=existing_cred.updated_at,
                    )
                raise EntityConflictException(f"Version {req.version} of credential '{req.credential_id}' already exists.")

            if req.version != existing_cred.current_version + 1:
                raise AppException(
                    message=f"Non-sequential version: expected {existing_cred.current_version + 1}, got {req.version}",
                    error_code="INVALID_VERSION_SEQUENCE",
                    status_code=400,
                )

            # Ensure new fingerprint is unique
            existing_fp = self.cred_repo.get_version_by_fingerprint(fingerprint)
            if existing_fp:
                raise EntityConflictException(f"Credential fingerprint '{fingerprint}' already exists.")

            # Supersede old version
            old_version_rec = self.cred_repo.get_version_by_number(req.credential_id, existing_cred.current_version)
            if old_version_rec:
                old_version_rec.superseded_by_fingerprint = fingerprint

            new_version_rec = CredentialVersion(
                credential_id=req.credential_id,
                version=req.version,
                fingerprint=fingerprint,
                idempotency_key=req.idempotency_key,
                document_digest=req.document_digest,
                metadata_digest=req.metadata_digest,
                merkle_root=req.merkle_root,
                expires_at=req.expires_at,
                issuance_status="PENDING",
            )
            existing_cred.current_version = req.version
            existing_cred.current_fingerprint = fingerprint
            self.cred_repo.add_version(new_version_rec)

            self.cred_repo.record_audit(
                event_type="CREDENTIAL_VERSION_SUPERSEDED",
                entity_type="CREDENTIAL",
                entity_id=req.credential_id,
                outcome="SUCCESS",
                correlation_id=correlation_id,
                details_json=json.dumps({"new_fingerprint": fingerprint, "version": req.version}),
            )
            self.db.commit()

            # Attempt on-chain anchoring if signer and contract are ready
            if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
                anchor_res = blockchain_client.anchor_credential_fingerprint(
                    credential_id_hex=req.credential_id,
                    doc_digest_hex=req.document_digest,
                    meta_digest_hex=req.metadata_digest,
                    merkle_root_hex=req.merkle_root,
                    version=req.version,
                    expires_at=req.expires_at or 0,
                )
                if anchor_res.get("status") == "CONFIRMED":
                    on_chain_fp = anchor_res.get("fingerprint")
                    on_chain_issuer = anchor_res.get("issuer_id")
                    if on_chain_fp and new_version_rec.fingerprint != on_chain_fp:
                        new_version_rec.fingerprint = on_chain_fp
                        existing_cred.current_fingerprint = on_chain_fp
                    if on_chain_issuer and existing_cred.issuer_id.lower() != on_chain_issuer.lower():
                        existing_cred.issuer_id = on_chain_issuer

                    new_version_rec.issuance_status = "CONFIRMED"
                    new_version_rec.issuance_tx_hash = anchor_res.get("tx_hash")
                    new_version_rec.block_number = anchor_res.get("block_number")
                    new_version_rec.chain_id = blockchain_client.chain_id
                    self.cred_repo.record_audit(
                        event_type="CREDENTIAL_ANCHORED_ON_CHAIN",
                        entity_type="CREDENTIAL",
                        entity_id=req.credential_id,
                        outcome="SUCCESS",
                        correlation_id=correlation_id,
                        details_json=json.dumps({
                            "fingerprint": new_version_rec.fingerprint,
                            "tx_hash": anchor_res.get("tx_hash"),
                            "block_number": anchor_res.get("block_number"),
                            "chain_id": blockchain_client.chain_id,
                        }),
                    )
                    self.db.commit()
                elif anchor_res.get("status") in ("REVERTED", "FAILED"):
                    new_version_rec.issuance_status = "FAILED"
                    new_version_rec.issuance_tx_hash = anchor_res.get("tx_hash")
                    self.cred_repo.record_audit(
                        event_type="CREDENTIAL_ANCHORING_FAILED",
                        entity_type="CREDENTIAL",
                        entity_id=req.credential_id,
                        outcome="FAILURE",
                        correlation_id=correlation_id,
                        details_json=json.dumps({
                            "fingerprint": fingerprint,
                            "error": anchor_res.get("error"),
                            "tx_hash": anchor_res.get("tx_hash"),
                        }),
                    )
                    self.db.commit()

            return CredentialResponse(
                credential_id=existing_cred.credential_id,
                issuer_id=existing_cred.issuer_id,
                current_version=existing_cred.current_version,
                current_fingerprint=existing_cred.current_fingerprint,
                current_status=existing_cred.current_status,
                issuance_status=new_version_rec.issuance_status,
                issuance_tx_hash=new_version_rec.issuance_tx_hash,
                created_at=existing_cred.created_at,
                updated_at=existing_cred.updated_at,
            )

    def get_credential(self, credential_id: str, principal: Optional[AuthenticatedPrincipal] = None) -> CredentialResponse:
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        if principal and not principal.is_admin() and not principal.has_role("verifier"):
            if principal.has_role("issuer") and principal.issuer_id:
                if cred.issuer_id.lower() != principal.issuer_id.lower():
                    raise AppException(
                        message="Forbidden: Access to another institution's credential is denied.",
                        error_code="TENANT_MISMATCH",
                        status_code=403,
                    )

        current_ver = self.cred_repo.get_version_by_number(credential_id, cred.current_version)
        issuance_st = current_ver.issuance_status if current_ver else "UNKNOWN"
        issuance_tx = current_ver.issuance_tx_hash if current_ver else None

        return CredentialResponse(
            credential_id=cred.credential_id,
            issuer_id=cred.issuer_id,
            current_version=cred.current_version,
            current_fingerprint=cred.current_fingerprint,
            current_status=cred.current_status,
            issuance_status=issuance_st,
            issuance_tx_hash=issuance_tx,
            created_at=cred.created_at,
            updated_at=cred.updated_at,
        )

    def list_credentials(
        self,
        limit: int = 50,
        offset: int = 0,
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> List[CredentialResponse]:
        issuer_filter = None
        if principal and not principal.is_admin() and not principal.has_role("verifier"):
            if principal.has_role("issuer") and principal.issuer_id:
                issuer_filter = principal.issuer_id

        creds = self.cred_repo.list_credentials(limit=limit, offset=offset, issuer_id=issuer_filter)
        results = []
        for cred in creds:
            current_ver = self.cred_repo.get_version_by_number(cred.credential_id, cred.current_version)
            results.append(
                CredentialResponse(
                    credential_id=cred.credential_id,
                    issuer_id=cred.issuer_id,
                    current_version=cred.current_version,
                    current_fingerprint=cred.current_fingerprint,
                    current_status=cred.current_status,
                    issuance_status=current_ver.issuance_status if current_ver else "UNKNOWN",
                    issuance_tx_hash=current_ver.issuance_tx_hash if current_ver else None,
                    created_at=cred.created_at,
                    updated_at=cred.updated_at,
                )
            )
        return results

    def get_credential_versions(self, credential_id: str, principal: Optional[AuthenticatedPrincipal] = None) -> List[CredentialVersionResponse]:
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        if principal and not principal.is_admin() and not principal.has_role("verifier"):
            if principal.has_role("issuer") and principal.issuer_id:
                if cred.issuer_id.lower() != principal.issuer_id.lower():
                    raise AppException(
                        message="Forbidden: Access to another institution's credential is denied.",
                        error_code="TENANT_MISMATCH",
                        status_code=403,
                    )

        versions = self.cred_repo.get_all_versions(credential_id)
        return [
            CredentialVersionResponse(
                credential_id=v.credential_id,
                version=v.version,
                fingerprint=v.fingerprint,
                document_digest=v.document_digest,
                metadata_digest=v.metadata_digest,
                merkle_root=v.merkle_root,
                expires_at=v.expires_at,
                issuance_status=v.issuance_status,
                issuance_tx_hash=v.issuance_tx_hash,
                block_number=v.block_number,
                chain_id=v.chain_id,
                superseded_by_fingerprint=v.superseded_by_fingerprint,
                created_at=v.created_at,
            )
            for v in versions
        ]

    def get_by_fingerprint(self, fingerprint: str, principal: Optional[AuthenticatedPrincipal] = None) -> CredentialResponse:
        version_rec = self.cred_repo.get_version_by_fingerprint(fingerprint)
        if not version_rec:
            raise EntityNotFoundException(f"Credential with fingerprint '{fingerprint}' was not found.")
        return self.get_credential(version_rec.credential_id, principal=principal)

    def verify_credential(self, fingerprint: str) -> VerificationResponse:
        """
        Verification pipeline:
        1. Query PostgreSQL metadata.
        2. Query on-chain CredentialRegistry via read-only call if available.
        3. Clearly report DB presence, blockchain availability, digest verification, and expiration status.
        Never fabricate valid: true if on-chain verification is unavailable.
        """
        now_ts = int(time.time())
        version_rec = self.cred_repo.get_version_by_fingerprint(fingerprint)
        checked_at = datetime.now(timezone.utc)

        if not version_rec:
            return VerificationResponse(
                fingerprint=fingerprint,
                database_found=False,
                blockchain_available=False,
                is_valid=False,
                details="Credential fingerprint not found in database.",
                checked_at=checked_at,
            )

        parent_cred = self.cred_repo.get_by_credential_id(version_rec.credential_id)
        lifecycle_st = parent_cred.current_status if parent_cred else "UNKNOWN"

        # Check expiration
        is_expired = False
        if version_rec.expires_at and version_rec.expires_at > 0:
            is_expired = now_ts >= version_rec.expires_at

        # Verify digest consistency against computed fingerprint
        recomputed_fp = compute_composite_fingerprint(
            document_digest=version_rec.document_digest,
            metadata_digest=version_rec.metadata_digest,
            merkle_root=version_rec.merkle_root,
            issuer_id=parent_cred.issuer_id if parent_cred else "",
            credential_id=version_rec.credential_id,
            version=version_rec.version,
        )
        digest_match = (recomputed_fp == fingerprint)

        # Attempt on-chain verification call
        chain_res = blockchain_client.verify_credential_on_chain(
            fingerprint_hex=fingerprint,
            doc_digest_hex=version_rec.document_digest,
            meta_digest_hex=version_rec.metadata_digest,
            merkle_root_hex=version_rec.merkle_root,
        )

        if chain_res is None:
            # Blockchain unavailable or contracts not deployed to configured RPC
            return VerificationResponse(
                fingerprint=fingerprint,
                database_found=True,
                blockchain_available=False,
                is_valid=False,  # DO NOT fabricate true without on-chain confirmation!
                lifecycle_status=lifecycle_st,
                is_expired=is_expired,
                digest_match=digest_match,
                blockchain_code="UNAVAILABLE",
                details="Database metadata confirmed and digests match, but blockchain network or contract is unavailable for cryptographic anchoring verification.",
                checked_at=checked_at,
            )

        is_valid_on_chain = chain_res.get("is_valid", False)
        chain_code = chain_res.get("code", "UNKNOWN")

        return VerificationResponse(
            fingerprint=fingerprint,
            database_found=True,
            blockchain_available=True,
            is_valid=is_valid_on_chain,
            lifecycle_status=chain_res.get("stored_status", lifecycle_st),
            is_expired=is_expired or (chain_code == "EXPIRED"),
            digest_match=digest_match and (chain_code != "HASH_MISMATCH"),
            blockchain_code=chain_code,
            details=f"Blockchain verified: status is {chain_res.get('stored_status')}, verification code is {chain_code}.",
            checked_at=checked_at,
        )

    def reconcile_and_anchor_credential(
        self,
        credential_id: str,
        version_number: int,
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> CredentialResponse:
        """
        Idempotent reconciliation and retry operation for pending credentials.
        1. Validates principal permissions and tenant boundary.
        2. Queries on-chain storage to detect if transaction previously confirmed on-chain.
        3. If not yet confirmed on-chain and signer is active, submits anchoring transaction.
        4. Synchronizes database state with verified on-chain confirmation.
        """
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        if principal and not principal.is_admin():
            if principal.has_role("issuer") and principal.issuer_id:
                if cred.issuer_id.lower() != principal.issuer_id.lower():
                    raise AppException(
                        message="Forbidden: Access to another institution's credential is denied.",
                        error_code="TENANT_MISMATCH",
                        status_code=403,
                    )

        version_rec = self.cred_repo.get_version_by_number(credential_id, version_number)
        if not version_rec:
            raise EntityNotFoundException(f"Version {version_number} of credential '{credential_id}' not found.")

        # Check on-chain record first (idempotent reconciliation)
        on_chain_rec = blockchain_client.get_credential_record_on_chain(version_rec.fingerprint)
        if not on_chain_rec or on_chain_rec.get("issued_at", 0) == 0:
            # Check by version using credential's issuer_id
            on_chain_rec = blockchain_client.get_credential_record_by_version(
                cred.issuer_id, credential_id, version_number
            )
            if not on_chain_rec or on_chain_rec.get("issued_at", 0) == 0:
                # If signer is configured with an accredited issuer, check using signer's issuer
                signer_issuer = blockchain_client.get_signer_issuer_id()
                if signer_issuer and signer_issuer.lower() != cred.issuer_id.lower():
                    on_chain_rec = blockchain_client.get_credential_record_by_version(
                        signer_issuer, credential_id, version_number
                    )

        if on_chain_rec and on_chain_rec.get("issued_at", 0) > 0:
            on_chain_fp = on_chain_rec.get("fingerprint")
            on_chain_issuer = on_chain_rec.get("issuer_id")

            # Update database to reflect authoritative on-chain state
            if on_chain_fp and version_rec.fingerprint != on_chain_fp:
                version_rec.fingerprint = on_chain_fp

            if cred.current_version == version_number and on_chain_fp:
                cred.current_fingerprint = on_chain_fp

            if on_chain_issuer and cred.issuer_id.lower() != on_chain_issuer.lower():
                cred.issuer_id = on_chain_issuer

            if version_rec.issuance_status != "CONFIRMED":
                version_rec.issuance_status = "CONFIRMED"
            version_rec.chain_id = blockchain_client.chain_id

            self.cred_repo.record_audit(
                event_type="CREDENTIAL_RECONCILED_ON_CHAIN",
                entity_type="CREDENTIAL",
                entity_id=credential_id,
                outcome="SUCCESS",
                correlation_id=str(uuid.uuid4()),
                details_json=json.dumps({
                    "fingerprint": version_rec.fingerprint,
                    "issuer_id": cred.issuer_id,
                    "on_chain": on_chain_rec,
                }),
            )
            self.db.commit()
            return self.get_credential(credential_id, principal=principal)

        # Attempt anchoring if signer and contract are ready
        if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
            res = blockchain_client.anchor_credential_fingerprint(
                credential_id_hex=credential_id,
                doc_digest_hex=version_rec.document_digest,
                meta_digest_hex=version_rec.metadata_digest,
                merkle_root_hex=version_rec.merkle_root,
                version=version_number,
                expires_at=version_rec.expires_at or 0,
            )
            if res.get("status") == "CONFIRMED":
                on_chain_fp = res.get("fingerprint")
                on_chain_issuer = res.get("issuer_id")
                if on_chain_fp and version_rec.fingerprint != on_chain_fp:
                    version_rec.fingerprint = on_chain_fp
                if cred.current_version == version_number and on_chain_fp:
                    cred.current_fingerprint = on_chain_fp
                if on_chain_issuer and cred.issuer_id.lower() != on_chain_issuer.lower():
                    cred.issuer_id = on_chain_issuer

                version_rec.issuance_status = "CONFIRMED"
                version_rec.issuance_tx_hash = res.get("tx_hash")
                version_rec.block_number = res.get("block_number")
                version_rec.chain_id = blockchain_client.chain_id
                self.cred_repo.record_audit(
                    event_type="CREDENTIAL_ANCHORED_ON_CHAIN",
                    entity_type="CREDENTIAL",
                    entity_id=credential_id,
                    outcome="SUCCESS",
                    correlation_id=str(uuid.uuid4()),
                    details_json=json.dumps({
                        "fingerprint": version_rec.fingerprint,
                        "tx_hash": res.get("tx_hash"),
                        "block_number": res.get("block_number"),
                        "chain_id": blockchain_client.chain_id,
                    }),
                )
                self.db.commit()
            elif res.get("status") in ("REVERTED", "FAILED"):
                version_rec.issuance_status = "FAILED"
                version_rec.issuance_tx_hash = res.get("tx_hash")
                self.cred_repo.record_audit(
                    event_type="CREDENTIAL_ANCHORING_FAILED",
                    entity_type="CREDENTIAL",
                    entity_id=credential_id,
                    outcome="FAILURE",
                    correlation_id=str(uuid.uuid4()),
                    details_json=json.dumps({"fingerprint": version_rec.fingerprint, "error": res.get("error")}),
                )
                self.db.commit()

        return self.get_credential(credential_id, principal=principal)

    def suspend_credential(
        self,
        credential_id: str,
        reason_code: int = 1,
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> CredentialResponse:
        """
        Transitions credential status from ACTIVE to SUSPENDED.
        Submits suspendCredential on-chain transaction if connected to EVM smart contracts.
        """
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        if principal and not principal.is_admin():
            if principal.has_role("issuer") and principal.issuer_id:
                if cred.issuer_id.lower() != principal.issuer_id.lower():
                    raise AppException(
                        message="Forbidden: Access to another institution's credential is denied.",
                        error_code="TENANT_MISMATCH",
                        status_code=403,
                    )

        if cred.current_status != "ACTIVE":
            raise InvalidLifecycleTransitionException(
                f"Cannot suspend credential in '{cred.current_status}' status. Only ACTIVE credentials may be suspended."
            )

        cred.current_status = "SUSPENDED"
        self.cred_repo.record_audit(
            event_type="CREDENTIAL_SUSPENDED",
            entity_type="CREDENTIAL",
            entity_id=credential_id,
            outcome="SUCCESS",
            correlation_id=str(uuid.uuid4()),
            details_json=json.dumps({"fingerprint": cred.current_fingerprint, "reason_code": reason_code}),
        )
        self.db.commit()

        # Submit on-chain suspension if connected
        if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
            res = blockchain_client.suspend_credential_on_chain(
                fingerprint_hex=cred.current_fingerprint,
                reason_code=reason_code,
            )
            if res.get("status") == "CONFIRMED":
                self.cred_repo.record_audit(
                    event_type="CREDENTIAL_SUSPENSION_ANCHORED_ON_CHAIN",
                    entity_type="CREDENTIAL",
                    entity_id=credential_id,
                    outcome="SUCCESS",
                    correlation_id=str(uuid.uuid4()),
                    details_json=json.dumps({"tx_hash": res.get("tx_hash"), "block_number": res.get("block_number")}),
                )
                self.db.commit()

        return self.get_credential(credential_id, principal=principal)

    def reactivate_credential(
        self,
        credential_id: str,
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> CredentialResponse:
        """
        Transitions credential status from SUSPENDED back to ACTIVE.
        Submits reactivateCredential on-chain transaction if connected to EVM smart contracts.
        """
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        if principal and not principal.is_admin():
            if principal.has_role("issuer") and principal.issuer_id:
                if cred.issuer_id.lower() != principal.issuer_id.lower():
                    raise AppException(
                        message="Forbidden: Access to another institution's credential is denied.",
                        error_code="TENANT_MISMATCH",
                        status_code=403,
                    )

        if cred.current_status != "SUSPENDED":
            raise InvalidLifecycleTransitionException(
                f"Cannot reactivate credential in '{cred.current_status}' status. Only SUSPENDED credentials may be reactivated."
            )

        cred.current_status = "ACTIVE"
        self.cred_repo.record_audit(
            event_type="CREDENTIAL_REACTIVATED",
            entity_type="CREDENTIAL",
            entity_id=credential_id,
            outcome="SUCCESS",
            correlation_id=str(uuid.uuid4()),
            details_json=json.dumps({"fingerprint": cred.current_fingerprint}),
        )
        self.db.commit()

        # Submit on-chain reactivation if connected
        if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
            res = blockchain_client.reactivate_credential_on_chain(
                fingerprint_hex=cred.current_fingerprint,
            )
            if res.get("status") == "CONFIRMED":
                self.cred_repo.record_audit(
                    event_type="CREDENTIAL_REACTIVATION_ANCHORED_ON_CHAIN",
                    entity_type="CREDENTIAL",
                    entity_id=credential_id,
                    outcome="SUCCESS",
                    correlation_id=str(uuid.uuid4()),
                    details_json=json.dumps({"tx_hash": res.get("tx_hash"), "block_number": res.get("block_number")}),
                )
                self.db.commit()

        return self.get_credential(credential_id, principal=principal)

