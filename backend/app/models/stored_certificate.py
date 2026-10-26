from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, utc_now


class StoredCertificate(Base):
    """
    Non-sensitive metadata registry for off-chain encrypted certificate files.
    Does NOT store encryption keys, salts, or plaintext certificates.
    """
    __tablename__ = "stored_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    storage_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    credential_id: Mapped[Optional[str]] = mapped_column(String(66), index=True, nullable=True)
    version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    document_digest: Mapped[str] = mapped_column(String(66), index=True, nullable=False)
    storage_adapter: Mapped[str] = mapped_column(String(32), default="filesystem_encrypted", nullable=False)
    envelope_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
