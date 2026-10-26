from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from app.models.verifier_challenge import VerifierChallenge
from app.db.base import utc_now


class ChallengeRepository:
    """
    Data access layer for Verifier Challenge persistence, state tracking, and atomic single-use consumption.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        challenge_id: str,
        challenge_hash: str,
        verifier_session_id: str,
        credential_fingerprint: Optional[str],
        expires_at: datetime,
        verifier_principal: str = "",
    ) -> VerifierChallenge:
        record = VerifierChallenge(
            challenge_id=challenge_id,
            challenge_hash=challenge_hash.lower(),
            verifier_session_id=verifier_session_id,
            verifier_principal=verifier_principal,
            credential_fingerprint=credential_fingerprint.lower() if credential_fingerprint else None,
            status="ISSUED",
            expires_at=expires_at,
            created_at=utc_now(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_challenge_id(self, challenge_id: str) -> Optional[VerifierChallenge]:
        stmt = select(VerifierChallenge).where(VerifierChallenge.challenge_id == challenge_id)
        return self.db.scalars(stmt).first()

    def get_by_challenge_hash(self, challenge_hash: str) -> Optional[VerifierChallenge]:
        stmt = select(VerifierChallenge).where(VerifierChallenge.challenge_hash == challenge_hash.lower())
        return self.db.scalars(stmt).first()

    def consume_atomically(
        self,
        challenge_id: str,
        challenge_hash: str,
        now: Optional[datetime] = None,
        verifier_principal: Optional[str] = None,
    ) -> bool:
        """
        Atomically transitions challenge from 'ISSUED' to 'CONSUMED' if unexpired.
        Returns True if successfully consumed by this call.
        Returns False if already consumed, expired, or non-matching (guarantees race condition safety).
        """
        current_time = now or utc_now()
        conditions = [
            VerifierChallenge.challenge_id == challenge_id,
            VerifierChallenge.challenge_hash == challenge_hash.lower(),
            VerifierChallenge.status == "ISSUED",
            VerifierChallenge.expires_at > current_time,
        ]
        if verifier_principal:
            conditions.append(VerifierChallenge.verifier_principal == verifier_principal)

        stmt = (
            update(VerifierChallenge)
            .where(*conditions)
            .values(
                status="CONSUMED",
                consumed_at=current_time,
            )
            .execution_options(synchronize_session=False)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount == 1
