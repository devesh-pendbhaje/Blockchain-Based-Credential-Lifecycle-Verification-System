import json
import uuid
import time
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.chain_operation import ChainOperation
from functools import wraps
from threading import RLock
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


# One local signing worker; serialize mutations and nonce allocation in this process.
_mutation_lock = RLock()
def serialized(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _mutation_lock:
            return fn(*args, **kwargs)
    return wrapped


class CredentialService:
    def __init__(self, db: Session):
        self.db = db
        self.cred_repo = CredentialRepository(db)
        self.issuer_repo = IssuerRepository(db)

    def _enforce_read_authorization(
        self,
        principal: Optional[AuthenticatedPrincipal],
        owner_issuer_id: str,
    ) -> None:
        if not principal:
            raise AppException(
                message="Authorization required. Provide 'Authorization: Bearer <token>' header.",
                error_code="UNAUTHORIZED",
                status_code=401,
            )
        if principal.is_admin() or principal.has_role("verifier"):
            return
        if principal.has_role("issuer"):
            if not principal.issuer_id:
                raise AppException(
                    message="Forbidden: Authenticated token is not bound to any institutional issuer authority.",
                    error_code="UNBOUND_ISSUER_IDENTITY",
                    status_code=403,
                )
            if principal.issuer_id.lower() != owner_issuer_id.lower():
                raise AppException(
                    message="Forbidden: Access to another institution's credential is denied.",
                    error_code="TENANT_MISMATCH",
                    status_code=403,
                )
            return
        raise AppException(
            message="Forbidden: Insufficient permissions to access this credential.",
            error_code="INSUFFICIENT_PERMISSIONS",
            status_code=403,
        )

    def _enforce_manage_authorization(
        self,
        principal: Optional[AuthenticatedPrincipal],
        owner_issuer_id: str,
    ) -> None:
        if not principal:
            raise AppException(
                message="Authorization required. Provide 'Authorization: Bearer <token>' header.",
                error_code="UNAUTHORIZED",
                status_code=401,
            )
        if principal.is_admin():
            return
        if principal.has_role("issuer"):
            if not principal.issuer_id:
                raise AppException(
                    message="Forbidden: Authenticated token is not bound to any institutional issuer authority.",
                    error_code="UNBOUND_ISSUER_IDENTITY",
                    status_code=403,
                )
            if principal.issuer_id.lower() != owner_issuer_id.lower():
                raise AppException(
                    message="Forbidden: Access to another institution's credential is denied.",
                    error_code="TENANT_MISMATCH",
                    status_code=403,
                )
            return
        raise AppException(
            message="Forbidden: Insufficient permissions to manage this credential.",
            error_code="INSUFFICIENT_PERMISSIONS",
            status_code=403,
        )

    def _credential(self, credential_id):
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential '{credential_id}' not found.")
        return cred

    def _latest_operation(self, credential_id):
        return self.db.scalars(select(ChainOperation).where(
            ChainOperation.credential_id == credential_id
        ).order_by(ChainOperation.created_at.desc())).first()

    def _response(self, cred):
        ver = self.cred_repo.get_version_by_number(cred.credential_id, cred.current_version)
        op = self._latest_operation(cred.credential_id)
        pending = self.db.scalars(select(CredentialVersion).where(
            CredentialVersion.credential_id == cred.credential_id,
            CredentialVersion.version > cred.current_version
        ).order_by(CredentialVersion.version.desc())).first()
        return CredentialResponse(
            credential_id=cred.credential_id, issuer_id=cred.issuer_id,
            current_version=cred.current_version, current_fingerprint=cred.current_fingerprint,
            current_status=cred.current_status, issuance_status=ver.issuance_status if ver else "PENDING",
            issuance_tx_hash=ver.issuance_tx_hash if ver else None,
            created_at=cred.created_at, updated_at=cred.updated_at,
            pending_version=pending.version if pending else None,
            operation_id=op.operation_id if op else None,
            operation_status=op.status if op else None,
            operation_tx_hash=op.tx_hash if op else None,
        )

    def _check_record(self, cred, ver, record):
        expected = dict(fingerprint=ver.fingerprint, issuer_id=cred.issuer_id,
                        credential_id=cred.credential_id, version=ver.version,
                        document_digest=ver.document_digest, metadata_digest=ver.metadata_digest,
                        merkle_root=ver.merkle_root, expires_at=ver.expires_at or 0)
        if any(record.get(k) != v for k, v in expected.items()):
            raise AppException("On-chain record does not match the complete expected credential.",
                               "RECONCILIATION_IDENTITY_MISMATCH", 409)
        if not record.get("issued_at") or record.get("status") not in {
            "ACTIVE", "SUSPENDED", "REVOKED", "SUPERSEDED", "ARCHIVED"
        }:
            raise AppException("Incomplete authoritative credential record.", "INVALID_CHAIN_RECORD", 503)

    def _confirm(self, cred, ver, op, record, result):
        self._check_record(cred, ver, record)
        if op.action in {"ISSUE", "SUPERSEDE"}:
            ver.issuance_status = "CONFIRMED"
            ver.issuance_tx_hash = op.tx_hash or ver.issuance_tx_hash
            ver.block_number = result.get("block_number") or ver.block_number
            ver.chain_id = blockchain_client.chain_id
            if ver.version > cred.current_version:
                old = self.cred_repo.get_version_by_number(cred.credential_id, ver.version - 1)
                if old:
                    old.superseded_by_fingerprint = ver.fingerprint
                cred.current_version = ver.version
                cred.current_fingerprint = ver.fingerprint
        if cred.current_version == ver.version:
            cred.current_status = record["status"]
        op.status = "CONFIRMED"
        op.error = None
        self.cred_repo.record_audit("CREDENTIAL_" + op.action + "_CONFIRMED", "CREDENTIAL",
                                   cred.credential_id, "SUCCESS", op.operation_id,
                                   json.dumps({"tx_hash": op.tx_hash, "version": ver.version}))
        self.db.commit()

    def _execute(self, cred, ver, op):
        # A known transaction hash is reconciled only; never blindly rebroadcast it.
        if op.status == "CONFIRMED":
            return
        if op.tx_hash:
            receipt = blockchain_client.get_transaction_receipt(op.tx_hash)
            if not receipt:
                op.status = "SUBMITTED"
                self.db.commit()
                return
            if receipt.get("status") == "REVERTED":
                op.status, op.error = "FAILED", "Transaction reverted on-chain"
                if op.action in {"ISSUE", "SUPERSEDE"}:
                    ver.issuance_status = "FAILED"
                self.db.commit()
                return
            record = blockchain_client.get_credential_record_on_chain(ver.fingerprint)
            if record:
                self._confirm(cred, ver, op, record, receipt)
            return
        if op.action in {"ISSUE", "SUPERSEDE"}:
            record = blockchain_client.get_credential_record_on_chain(ver.fingerprint)
            if record and record.get("issued_at"):
                self._confirm(cred, ver, op, record, {})
                return
        if not blockchain_client.can_transact or not blockchain_client.is_contract_ready("credential"):
            raise AppException("Blockchain is unavailable; no lifecycle change was completed.",
                               "BLOCKCHAIN_UNAVAILABLE", 503)

        def persist_hash(tx_hash):
            # Called before broadcasting signed bytes, so a crash cannot lose the hash.
            op.tx_hash, op.status = tx_hash, "SUBMITTED"
            if op.action in {"ISSUE", "SUPERSEDE"}:
                ver.issuance_tx_hash = tx_hash
            self.db.commit()

        kwargs = dict(expected_issuer_id=cred.issuer_id, on_broadcast=persist_hash)
        if op.action in {"ISSUE", "SUPERSEDE"}:
            kwargs.update(doc_digest_hex=ver.document_digest, meta_digest_hex=ver.metadata_digest,
                          merkle_root_hex=ver.merkle_root, expires_at=ver.expires_at or 0)
            if op.action == "ISSUE":
                result = blockchain_client.anchor_credential_fingerprint(
                    credential_id_hex=cred.credential_id, version=ver.version, **kwargs)
            else:
                old = self.cred_repo.get_version_by_number(cred.credential_id, ver.version - 1)
                result = blockchain_client.supersede_credential_on_chain(old_fingerprint_hex=old.fingerprint, **kwargs)
        else:
            kwargs["fingerprint_hex"] = ver.fingerprint
            if op.action != "REACTIVATE":
                kwargs["reason_code"] = op.reason_code
            result = getattr(blockchain_client, op.action.lower() + "_credential_on_chain")(**kwargs)
        op.tx_hash = result.get("tx_hash") or op.tx_hash
        if op.action in {"ISSUE", "SUPERSEDE"}:
            ver.issuance_tx_hash = op.tx_hash
        if result.get("status") == "CONFIRMED":
            record = blockchain_client.get_credential_record_on_chain(ver.fingerprint)
            if record:
                self._confirm(cred, ver, op, record, result)
                return
            # Receipt alone does not establish identity or final lifecycle state.
            op.status, op.error = "SUBMITTED", "Awaiting authoritative record"
        elif result.get("status") in {"PENDING", "UNCERTAIN"}:
            op.status, op.error = "SUBMITTED", "Awaiting transaction confirmation"
        else:
            op.status, op.error = "FAILED", str(result.get("error", "Transaction failed"))[:1024]
            if op.action in {"ISSUE", "SUPERSEDE"}:
                ver.issuance_status = "FAILED"
        self.db.commit()
        if op.status == "FAILED":
            raise AppException(op.error, "LIFECYCLE_TRANSACTION_FAILED", 502)

    def _operation(self, cred, ver, action, reason=1):
        active = self.db.scalars(select(ChainOperation).where(
            ChainOperation.credential_id == cred.credential_id,
            ChainOperation.status.in_(["PREPARED", "SUBMITTED"])
        )).first()
        if active:
            if (active.action, active.version) != (action, ver.version):
                raise EntityConflictException("Reconcile the pending operation before another lifecycle change.")
            return active
        op = ChainOperation(credential_id=cred.credential_id, version=ver.version,
                            action=action, reason_code=reason, status="PREPARED")
        self.db.add(op)
        self.db.commit()
        return op

    @serialized
    def create_credential(self, req, principal=None):
        cred = self.cred_repo.get_by_credential_id(req.credential_id)
        self._enforce_manage_authorization(principal, cred.issuer_id if cred else req.issuer_id)
        if cred and cred.issuer_id != req.issuer_id:
            raise AppException("Cannot add a version to another issuer's credential.", "TENANT_MISMATCH", 403)
        issuer = self.issuer_repo.get_by_issuer_id(req.issuer_id)
        if not issuer:
            raise EntityNotFoundException(f"Issuer '{req.issuer_id}' not found.")
        if issuer.status != "ACTIVE":
            raise AppException("Issuer is not active.", "ISSUER_REVOKED" if issuer.status == "REVOKED" else "ISSUER_INACTIVE", 400)
        fp = compute_composite_fingerprint(req.document_digest, req.metadata_digest, req.merkle_root,
                                           req.issuer_id, req.credential_id, req.version)
        previous_key = self.cred_repo.get_version_by_idempotency_key(req.idempotency_key) if req.idempotency_key else None
        if previous_key and (previous_key.fingerprint != fp or (previous_key.expires_at or 0) != (req.expires_at or 0)):
            raise EntityConflictException("Idempotency key has already been used for a different credential issuance request.")
        existing = self.cred_repo.get_version_by_number(req.credential_id, req.version)
        if existing:
            if existing.fingerprint != fp or (existing.expires_at or 0) != (req.expires_at or 0):
                raise EntityConflictException("Credential version already exists with different content or expiry.")
            return self._response(cred)
        if not cred and req.version != 1:
            raise AppException("Initial credential issuance must be version 1.", "INVALID_VERSION", 400)
        if cred and req.version != cred.current_version + 1:
            raise AppException("Versions must be sequential.", "INVALID_VERSION_SEQUENCE", 400)
        if cred:
            if cred.current_status != "ACTIVE":
                raise InvalidLifecycleTransitionException("Only a confirmed ACTIVE credential can be superseded.")
            if self.db.scalars(select(ChainOperation).where(ChainOperation.credential_id == cred.credential_id,
                    ChainOperation.status.in_(["PREPARED", "SUBMITTED"]))).first():
                raise EntityConflictException("Reconcile the pending operation first.")
        else:
            cred = Credential(credential_id=req.credential_id, issuer_id=req.issuer_id,
                              current_version=1, current_fingerprint=fp, current_status="PENDING")
            self.db.add(cred)
            self.db.flush()
        ver = CredentialVersion(credential_id=req.credential_id, version=req.version, fingerprint=fp,
                idempotency_key=req.idempotency_key, document_digest=req.document_digest,
                metadata_digest=req.metadata_digest, merkle_root=req.merkle_root,
                expires_at=req.expires_at or 0, issuance_status="PENDING")
        self.db.add(ver)
        self.db.commit()
        op = self._operation(cred, ver, "ISSUE" if req.version == 1 else "SUPERSEDE")
        if blockchain_client.can_transact and blockchain_client.is_contract_ready("credential"):
            self._execute(cred, ver, op)
        return self._response(cred)

    @serialized
    def reconcile_and_anchor_credential(self, credential_id, version_number, principal=None):
        cred = self._credential(credential_id)
        self._enforce_manage_authorization(principal, cred.issuer_id)
        ver = self.cred_repo.get_version_by_number(credential_id, version_number)
        if not ver:
            raise EntityNotFoundException("Credential version not found.")
        op = self._latest_operation(credential_id)
        if not op or op.version != version_number or op.status == "FAILED":
            op = self._operation(cred, ver, "ISSUE" if version_number == 1 else "SUPERSEDE")
            # Preserve hashes from pre-operation-table versions during migration.
            op.tx_hash = ver.issuance_tx_hash
        if op.status == "CONFIRMED":
            record = blockchain_client.get_credential_record_on_chain(ver.fingerprint)
            if not record:
                raise AppException("Authoritative record unavailable.", "BLOCKCHAIN_UNAVAILABLE", 503)
            self._confirm(cred, ver, op, record, {})
        else:
            self._execute(cred, ver, op)
        return self._response(cred)

    @serialized
    def _lifecycle(self, credential_id, action, principal, reason=1):
        cred = self._credential(credential_id)
        self._enforce_manage_authorization(principal, cred.issuer_id)
        latest = self._latest_operation(credential_id)
        ver = self.cred_repo.get_version_by_number(credential_id, cred.current_version)
        if latest and latest.status in {"PREPARED", "SUBMITTED"}:
            if latest.action != action:
                raise EntityConflictException("Reconcile the pending operation first.")
            self._execute(cred, ver, latest)
            return self._response(cred)
        allowed = {"SUSPEND": {"ACTIVE"}, "REACTIVATE": {"SUSPENDED"}, "REVOKE": {"ACTIVE", "SUSPENDED"}}
        if cred.current_status not in allowed[action]:
            raise InvalidLifecycleTransitionException(f"Cannot {action.lower()} a {cred.current_status} credential.")
        if not blockchain_client.can_transact or not blockchain_client.is_contract_ready("credential"):
            raise AppException("Blockchain is unavailable; no lifecycle change was completed.", "BLOCKCHAIN_UNAVAILABLE", 503)
        op = self._operation(cred, ver, action, reason)
        self._execute(cred, ver, op)
        return self._response(cred)

    def suspend_credential(self, credential_id, reason_code=1, principal=None):
        return self._lifecycle(credential_id, "SUSPEND", principal, reason_code)

    def reactivate_credential(self, credential_id, principal=None):
        return self._lifecycle(credential_id, "REACTIVATE", principal)

    def revoke_credential(self, credential_id, reason_code=1, principal=None):
        return self._lifecycle(credential_id, "REVOKE", principal, reason_code)

    def get_credential(self, credential_id: str, principal: Optional[AuthenticatedPrincipal] = None) -> CredentialResponse:
        cred = self.cred_repo.get_by_credential_id(credential_id)
        if not cred:
            raise EntityNotFoundException(f"Credential with ID '{credential_id}' was not found.")

        self._enforce_read_authorization(principal, cred.issuer_id)

        return self._response(cred)

    def list_credentials(
        self,
        limit: int = 50,
        offset: int = 0,
        principal: Optional[AuthenticatedPrincipal] = None,
    ) -> List[CredentialResponse]:
        if not principal:
            raise AppException(
                message="Authorization required. Provide 'Authorization: Bearer <token>' header.",
                error_code="UNAUTHORIZED",
                status_code=401,
            )
        if principal.is_admin() or principal.has_role("verifier"):
            issuer_filter = None
        elif principal.has_role("issuer"):
            if not principal.issuer_id:
                raise AppException(
                    message="Forbidden: Authenticated token is not bound to any institutional issuer authority.",
                    error_code="UNBOUND_ISSUER_IDENTITY",
                    status_code=403,
                )
            issuer_filter = principal.issuer_id
        else:
            raise AppException(
                message="Forbidden: Insufficient permissions to list credentials.",
                error_code="INSUFFICIENT_PERMISSIONS",
                status_code=403,
            )

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

        self._enforce_read_authorization(principal, cred.issuer_id)

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
            is_valid=bool(is_valid_on_chain and digest_match and not is_expired),
            lifecycle_status=chain_res.get("stored_status", lifecycle_st),
            is_expired=is_expired or (chain_code == "EXPIRED"),
            digest_match=digest_match and (chain_code != "HASH_MISMATCH"),
            blockchain_code=chain_code,
            details=f"Blockchain verified: status is {chain_res.get('stored_status')}, verification code is {chain_code}.",
            checked_at=checked_at,
        )

