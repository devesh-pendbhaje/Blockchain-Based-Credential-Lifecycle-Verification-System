from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, utc_now


class VerifierChallenge(Base):
    """
    Durable verifier challenge entity for replay protection and session binding.
    Stores the SHA-256 hash of the challenge nonce rather than raw plaintext nonce.
    """
    __tablename__ = "verifier_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    challenge_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    challenge_hash: Mapped[str] = mapped_column(String(66), unique=True, index=True, nullable=False)
    verifier_session_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    verifier_principal: Mapped[str] = mapped_column(String(256), index=True, nullable=False, default="")
    credential_fingerprint: Mapped[Optional[str]] = mapped_column(String(66), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ISSUED", nullable=False)  # ISSUED, CONSUMED, EXPIRED
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
