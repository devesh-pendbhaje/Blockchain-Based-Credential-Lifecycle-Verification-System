from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.credential import Credential
from app.models.credential_version import CredentialVersion
from app.models.audit_event import AuditEvent


class CredentialRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_credential_id(self, credential_id: str) -> Optional[Credential]:
        stmt = select(Credential).where(Credential.credential_id == credential_id)
        return self.db.scalars(stmt).first()

    def get_version_by_fingerprint(self, fingerprint: str) -> Optional[CredentialVersion]:
        stmt = select(CredentialVersion).where(CredentialVersion.fingerprint == fingerprint)
        return self.db.scalars(stmt).first()

    def get_by_fingerprint(self, fingerprint: str) -> Optional[Credential]:
        stmt = select(Credential).where(Credential.current_fingerprint == fingerprint)
        return self.db.scalars(stmt).first()

    def get_version_by_number(self, credential_id: str, version: int) -> Optional[CredentialVersion]:
        stmt = select(CredentialVersion).where(
            CredentialVersion.credential_id == credential_id,
            CredentialVersion.version == version,
        )
        return self.db.scalars(stmt).first()

    def get_version_by_idempotency_key(self, idempotency_key: str) -> Optional[CredentialVersion]:
        if not idempotency_key:
            return None
        stmt = select(CredentialVersion).where(CredentialVersion.idempotency_key == idempotency_key)
        return self.db.scalars(stmt).first()

    def get_all_versions(self, credential_id: str) -> List[CredentialVersion]:
        stmt = (
            select(CredentialVersion)
            .where(CredentialVersion.credential_id == credential_id)
            .order_by(CredentialVersion.version.asc())
        )
        return list(self.db.scalars(stmt).all())

    def list_credentials(
        self, limit: int = 50, offset: int = 0, issuer_id: Optional[str] = None
    ) -> List[Credential]:
        stmt = select(Credential)
        if issuer_id:
            stmt = stmt.where(Credential.issuer_id == issuer_id)
        stmt = stmt.order_by(Credential.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt).all())

    def create_credential(
        self, credential: Credential, version_record: CredentialVersion
    ) -> Tuple[Credential, CredentialVersion]:
        self.db.add(credential)
        self.db.flush()
        self.db.add(version_record)
        self.db.flush()
        return credential, version_record

    def add_version(self, version_record: CredentialVersion) -> CredentialVersion:
        self.db.add(version_record)
        self.db.flush()
        return version_record

    def record_audit(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        outcome: str,
        correlation_id: str,
        details_json: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            outcome=outcome,
            correlation_id=correlation_id,
            details_json=details_json,
        )
        self.db.add(event)
        self.db.flush()
        return event
