from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, utc_now


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    credential_id: Mapped[str] = mapped_column(String(66), unique=True, index=True, nullable=False)
    issuer_id: Mapped[str] = mapped_column(String(66), ForeignKey("issuers.issuer_id", ondelete="RESTRICT"), index=True, nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    current_fingerprint: Mapped[str] = mapped_column(String(66), unique=True, index=True, nullable=False)
    current_status: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    issuer: Mapped["Issuer"] = relationship("Issuer", back_populates="credentials")
    versions: Mapped[List["CredentialVersion"]] = relationship(
        "CredentialVersion",
        back_populates="credential",
        cascade="all, delete-orphan",
        order_by="CredentialVersion.version.asc()",
    )
