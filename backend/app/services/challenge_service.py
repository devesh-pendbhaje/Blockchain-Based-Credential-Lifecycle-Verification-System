import hmac
import uuid
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.exceptions import AppException
from app.repositories.challenge_repository import ChallengeRepository
from app.db.base import utc_now, ensure_utc


class ChallengeService:
    """
    Verifier challenge-response service providing single-use, session-scoped,
    cryptographically random nonce challenges to prevent presentation replay attacks.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ChallengeRepository(db)

    def _hash_nonce(self, nonce_hex: str) -> str:
        clean = nonce_hex.strip().lower()
        if clean.startswith("0x"):
            clean = clean[2:]
        if len(clean) != 64:
            raise AppException(
                message=f"Challenge nonce must be exactly 256 bits (64 hex characters), got {len(clean)}.",
                error_code="INVALID_CHALLENGE_NONCE_LENGTH",
                status_code=400,
            )
        try:
            raw_bytes = bytes.fromhex(clean)
        except ValueError as exc:
            raise AppException(
                message="Challenge nonce must be valid hexadecimal.",
                error_code="INVALID_CHALLENGE_HEX",
                status_code=400,
            ) from exc
        return "0x" + hashlib.sha256(raw_bytes).hexdigest().lower()

    def create_challenge(
        self,
        verifier_session_id: str,
        credential_fingerprint: Optional[str] = None,
        expiry_seconds: Optional[int] = None,
        verifier_principal: str = "",
    ) -> Dict[str, Any]:
        """
        Generates an unpredictable 256-bit random nonce challenge bound to an authenticated verifier principal and session.
        Stores only the SHA-256 hash of the nonce in PostgreSQL.
        Returns the plaintext nonce to the caller upon issuance.
        """
        if not verifier_session_id or not verifier_session_id.strip():
            raise AppException(
                message="Verifier session ID is required.",
                error_code="MISSING_VERIFIER_SESSION",
                status_code=400,
            )

        # 1. 256 bits of cryptographically secure randomness
        nonce_hex = secrets.token_hex(32)  # 64 hex characters
        challenge_hash = self._hash_nonce(nonce_hex)
        challenge_id = str(uuid.uuid4())

        duration = expiry_seconds or settings.CHALLENGE_EXPIRY_SECONDS
        expires_at = utc_now() + timedelta(seconds=duration)

        # 2. Persist to database bound to verifier principal
        record = self.repo.create(
            challenge_id=challenge_id,
            challenge_hash=challenge_hash,
            verifier_session_id=verifier_session_id.strip(),
            verifier_principal=verifier_principal.strip() if verifier_principal else "",
            credential_fingerprint=credential_fingerprint.strip().lower() if credential_fingerprint else None,
            expires_at=expires_at,
        )

        return {
            "challenge_id": challenge_id,
            "challenge_nonce": "0x" + nonce_hex,  # Returned only once to requester
            "verifier_session_id": record.verifier_session_id,
            "verifier_principal": record.verifier_principal,
            "credential_fingerprint": record.credential_fingerprint,
            "expires_at": record.expires_at,
            "status": record.status,
        }

    def validate_and_consume_challenge(
        self,
        challenge_id: str,
        challenge_nonce: str,
        verifier_session_id: str,
        credential_fingerprint: Optional[str] = None,
        verifier_principal: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validates challenge existence, binding, expiration, and consumes it atomically.
        Guarantees single-use behavior across concurrent submission attempts.
        """
        record = self.repo.get_by_challenge_id(challenge_id)
        if not record:
            raise AppException(
                message=f"Challenge '{challenge_id}' not found.",
                error_code="CHALLENGE_NOT_FOUND",
                status_code=404,
            )

        now = utc_now()

        # Check status before consumption
        if record.status == "CONSUMED":
            raise AppException(
                message=f"Challenge '{challenge_id}' has already been consumed. Replay attempt rejected.",
                error_code="CHALLENGE_ALREADY_CONSUMED",
                status_code=409,
            )

        if record.status == "EXPIRED" or ensure_utc(record.expires_at) <= now:
            raise AppException(
                message=f"Challenge '{challenge_id}' has expired.",
                error_code="CHALLENGE_EXPIRED",
                status_code=410,
            )

        # Constant-time comparison of challenge hash
        provided_hash = self._hash_nonce(challenge_nonce)
        if not hmac.compare_digest(provided_hash.lower(), record.challenge_hash.lower()):
            raise AppException(
                message="Incorrect challenge nonce.",
                error_code="INVALID_CHALLENGE_NONCE",
                status_code=400,
            )

        # Verifier principal binding check (Cross-verifier attack prevention)
        if record.verifier_principal:
            if not verifier_principal or record.verifier_principal.strip() != verifier_principal.strip():
                raise AppException(
                    message="Challenge was issued to a different verifier principal. Cross-verifier consumption rejected.",
                    error_code="VERIFIER_PRINCIPAL_MISMATCH",
                    status_code=403,
                )

        # Verifier session binding check
        if record.verifier_session_id != verifier_session_id.strip():
            raise AppException(
                message="Verifier session mismatch for challenge.",
                error_code="VERIFIER_SESSION_MISMATCH",
                status_code=403,
            )

        # Credential fingerprint scope check if bound at issuance
        if record.credential_fingerprint:
            if not credential_fingerprint or (
                record.credential_fingerprint.lower() != credential_fingerprint.strip().lower()
            ):
                raise AppException(
                    message="Challenge is not scoped for this credential fingerprint.",
                    error_code="CHALLENGE_SCOPE_MISMATCH",
                    status_code=403,
                )

        # Atomic single-use consumption
        success = self.repo.consume_atomically(
            challenge_id,
            provided_hash,
            now=now,
            verifier_principal=verifier_principal,
        )
        if not success:
            raise AppException(
                message="Failed to consume challenge. Challenge was consumed concurrently or expired.",
                error_code="CHALLENGE_CONCURRENT_CONSUMPTION",
                status_code=409,
            )

        return {
            "challenge_id": challenge_id,
            "status": "CONSUMED",
            "consumed_at": now,
            "verifier_session_id": record.verifier_session_id,
        }
