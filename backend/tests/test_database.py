import pytest
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.issuer import Issuer
from app.models.credential import Credential
from app.models.credential_version import CredentialVersion
from app.models.audit_event import AuditEvent


def test_model_relationships_and_cascades(db_session: Session):
    issuer_id = "0x" + "11" * 32
    cred_id = "0x" + "22" * 32
    fp1 = "0x" + "33" * 32

    # 1. Create Issuer
    issuer = Issuer(issuer_id=issuer_id, display_name="Test University", status="ACTIVE")
    db_session.add(issuer)
    db_session.commit()

    # 2. Create Credential and Version
    cred = Credential(
        credential_id=cred_id,
        issuer_id=issuer_id,
        current_version=1,
        current_fingerprint=fp1,
        current_status="ACTIVE",
    )
    ver = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint=fp1,
        document_digest="0x" + "44" * 32,
        metadata_digest="0x" + "55" * 32,
        merkle_root="0x" + "66" * 32,
        expires_at=0,
        issuance_status="CONFIRMED",
    )
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    # Query back
    fetched_issuer = db_session.query(Issuer).filter_by(issuer_id=issuer_id).first()
    assert fetched_issuer is not None
    assert len(fetched_issuer.credentials) == 1
    assert fetched_issuer.credentials[0].credential_id == cred_id
    assert len(fetched_issuer.credentials[0].versions) == 1
    assert fetched_issuer.credentials[0].versions[0].fingerprint == fp1


def test_unique_constraints(db_session: Session):
    issuer_id = "0x" + "aa" * 32
    cred_id = "0x" + "bb" * 32
    fp1 = "0x" + "cc" * 32

    issuer1 = Issuer(issuer_id=issuer_id, display_name="Uni 1")
    db_session.add(issuer1)
    db_session.commit()

    # Duplicate issuer_id must fail
    issuer2 = Issuer(issuer_id=issuer_id, display_name="Uni 2")
    db_session.add(issuer2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Add valid credential
    cred1 = Credential(
        credential_id=cred_id,
        issuer_id=issuer_id,
        current_version=1,
        current_fingerprint=fp1,
    )
    ver1 = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint=fp1,
        document_digest="0x" + "01" * 32,
        metadata_digest="0x" + "02" * 32,
        merkle_root="0x" + "03" * 32,
    )
    db_session.add(cred1)
    db_session.add(ver1)
    db_session.commit()

    # Duplicate (credential_id, version) must fail
    ver1_dup = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint="0x" + "dd" * 32,
        document_digest="0x" + "01" * 32,
        metadata_digest="0x" + "02" * 32,
        merkle_root="0x" + "03" * 32,
    )
    db_session.add(ver1_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_audit_event_logging(db_session: Session):
    audit = AuditEvent(
        event_type="TEST_EVENT",
        entity_type="CREDENTIAL",
        entity_id="0x" + "99" * 32,
        outcome="SUCCESS",
        correlation_id="corr-1234",
        details_json='{"test": true}',
    )
    db_session.add(audit)
    db_session.commit()

    saved = db_session.query(AuditEvent).filter_by(correlation_id="corr-1234").first()
    assert saved is not None
    assert saved.event_type == "TEST_EVENT"


def test_idempotency_key_db_uniqueness(db_session: Session):
    issuer_id = "0x" + "11" * 32
    cred_id = "0x" + "22" * 32
    cred_id2 = "0x" + "33" * 32

    issuer = Issuer(issuer_id=issuer_id, display_name="Test Uni")
    db_session.add(issuer)
    db_session.commit()

    cred1 = Credential(
        credential_id=cred_id,
        issuer_id=issuer_id,
        current_version=1,
        current_fingerprint="0x" + "44" * 32,
    )
    ver1 = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint="0x" + "44" * 32,
        idempotency_key="unique-idemp-key-1",
        document_digest="0x" + "01" * 32,
        metadata_digest="0x" + "02" * 32,
        merkle_root="0x" + "03" * 32,
    )
    db_session.add(cred1)
    db_session.add(ver1)
    db_session.commit()

    # Reusing the exact same idempotency_key on a different credential must violate unique constraint
    cred2 = Credential(
        credential_id=cred_id2,
        issuer_id=issuer_id,
        current_version=1,
        current_fingerprint="0x" + "55" * 32,
    )
    ver2 = CredentialVersion(
        credential_id=cred_id2,
        version=1,
        fingerprint="0x" + "55" * 32,
        idempotency_key="unique-idemp-key-1",  # Duplicate key!
        document_digest="0x" + "01" * 32,
        metadata_digest="0x" + "02" * 32,
        merkle_root="0x" + "03" * 32,
    )
    db_session.add(cred2)
    db_session.add(ver2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

