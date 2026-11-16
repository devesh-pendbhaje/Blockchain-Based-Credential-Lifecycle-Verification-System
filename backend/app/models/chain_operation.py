import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, utc_now


class ChainOperation(Base):
    """Durable transaction intent; a submitted hash must never be blindly retried."""
    __tablename__ = "chain_operations"
    operation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    credential_id: Mapped[str] = mapped_column(String(66), ForeignKey("credentials.credential_id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PREPARED")
    reason_code: Mapped[int] = mapped_column(Integer, default=1)
    tx_hash: Mapped[Optional[str]] = mapped_column(String(66), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
