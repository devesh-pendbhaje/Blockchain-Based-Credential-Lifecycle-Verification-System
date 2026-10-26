from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.stored_certificate import StoredCertificate
from app.db.base import utc_now


class StorageRepository:
    """
    Data access layer for non-sensitive off-chain stored certificate metadata.
    """

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        storage_id: str,
        document_digest: str,
        content_type: str,
        byte_size: int,
        credential_id: Optional[str] = None,
        version: Optional[int] = None,
        storage_adapter: str = "filesystem_encrypted",
        envelope_version: int = 1,
    ) -> StoredCertificate:
        record = StoredCertificate(
            storage_id=storage_id,
            credential_id=credential_id,
            version=version,
            document_digest=document_digest.lower(),
            storage_adapter=storage_adapter,
            envelope_version=envelope_version,
            content_type=content_type,
            byte_size=byte_size,
            created_at=utc_now(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_storage_id(self, storage_id: str) -> Optional[StoredCertificate]:
        stmt = select(StoredCertificate).where(StoredCertificate.storage_id == storage_id)
        return self.db.scalars(stmt).first()

    def get_by_credential(self, credential_id: str, version: int) -> Optional[StoredCertificate]:
        stmt = select(StoredCertificate).where(
            StoredCertificate.credential_id == credential_id,
            StoredCertificate.version == version,
        )
        return self.db.scalars(stmt).first()

    def get_by_digest(self, document_digest: str) -> List[StoredCertificate]:
        stmt = select(StoredCertificate).where(
            StoredCertificate.document_digest == document_digest.lower()
        )
        return list(self.db.scalars(stmt).all())
