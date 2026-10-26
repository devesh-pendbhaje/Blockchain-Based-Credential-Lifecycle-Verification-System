from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class CredentialVersion(Base):
    __tablename__ = "credential_versions"
    __table_args__ = (
        UniqueConstraint("credential_id", "version", name="uq_credential_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[str] = mapped_column(String(66), ForeignKey("credentials.credential_id", ondelete="RESTRICT"), index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(66), unique=True, index=True, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), unique=True, index=True, nullable=True)
    document_digest: Mapped[str] = mapped_column(String(66), nullable=False)
    metadata_digest: Mapped[str] = mapped_column(String(66), nullable=False)
    merkle_root: Mapped[str] = mapped_column(String(66), nullable=False)
    expires_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=0)
    issuance_tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True, index=True)
    issuance_status: Mapped[str] = mapped_column(String(32), nullable=False, default="PENDING")
    block_number: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    chain_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    superseded_by_fingerprint: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    credential: Mapped["Credential"] = relationship("Credential", back_populates="versions")
