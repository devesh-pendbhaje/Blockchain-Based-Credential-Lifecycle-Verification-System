import pytest
from typing import Generator
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

import sys
from pathlib import Path

# Ensure backend root is always on sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app
from app.db.base import Base
from app.db.session import get_db

import os
import tempfile

# Temporary SQLite database file to provide isolated, thread-safe connection pooling
_test_db_file = os.path.join(tempfile.gettempdir(), f"bc_test_{os.getpid()}.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_test_db_file}"

engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Creates fresh schema tables in the in-memory test database for every test function,
    and drops all tables on teardown to prevent state pollution.
    """
    Base.metadata.create_all(bind=engine_test)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine_test)


import time
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.config import settings

# Deterministic test RSA keypair for automated security tests
_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_test_private_pem = _test_private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode("utf-8")

_test_public_key = _test_private_key.public_key()
_test_public_pem = _test_public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode("utf-8")

# Set dev keypair in settings for the test process
settings.AUTH_DEV_PUBLIC_KEY = _test_public_pem
settings.AUTH_DEV_PRIVATE_KEY = _test_private_pem
settings.OIDC_ISSUER_URL = "https://idp.institution.example.org"
settings.OIDC_AUDIENCE = "credential-verification-api"
settings.AUTH_MODE = "local_dev"
settings.ENVIRONMENT = "development"

# Isolate blockchain client during standard automated unit/regression tests to prevent live RPC calls
settings.BLOCKCHAIN_RPC_URL = "http://127.0.0.1:8545"
settings.BLOCKCHAIN_TIMEOUT_SECONDS = 0.5
settings.BLOCKCHAIN_SIGNER_PRIVATE_KEY = None

from app.blockchain.client import blockchain_client
blockchain_client.signer_account = None
blockchain_client.signer_address = None
blockchain_client.can_transact = False
blockchain_client._cached_connected = False
blockchain_client.timeout = 0.5


@pytest.fixture(scope="session")
def test_rsa_keys():
    return {
        "private_pem": _test_private_pem,
        "public_pem": _test_public_pem,
        "private_key": _test_private_key,
        "public_key": _test_public_key,
    }


def create_test_jwt(
    sub: str = "test-subject",
    roles: list = None,
    issuer_id: str = None,
    verifier_id: str = None,
    issuer: str = "https://idp.institution.example.org",
    audience: str = "credential-verification-api",
    exp_offset: int = 3600,
    alg: str = "RS256",
    kid: str = "test-key-1",
    private_pem: str = _test_private_pem,
    extra_claims: dict = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "aud": audience,
        "sub": sub,
        "iat": now,
        "nbf": now - 5,
        "exp": now + exp_offset,
        "roles": roles or ["user"],
    }
    if issuer_id:
        payload["issuer_id"] = issuer_id
    if verifier_id:
        payload["verifier_id"] = verifier_id
    if extra_claims:
        payload.update(extra_claims)

    headers = {"kid": kid, "alg": alg}
    return jwt.encode(payload, private_pem, algorithm=alg, headers=headers)


@pytest.fixture
def make_token():
    return create_test_jwt


@pytest.fixture
def admin_headers():
    tok = create_test_jwt(
        sub="admin-sec-ops",
        roles=["admin", "issuer", "verifier"],
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def issuer_headers():
    tok = create_test_jwt(
        sub="issuer-authority-01",
        roles=["issuer"],
        issuer_id="0x" + "11" * 32,
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def other_issuer_headers():
    tok = create_test_jwt(
        sub="issuer-authority-02",
        roles=["issuer"],
        issuer_id="0x" + "22" * 32,
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def verifier_headers():
    tok = create_test_jwt(
        sub="verifier-auditor-01",
        roles=["verifier"],
        verifier_id="verifier-auditor-01",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def other_verifier_headers():
    tok = create_test_jwt(
        sub="verifier-auditor-02",
        roles=["verifier"],
        verifier_id="verifier-auditor-02",
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def user_headers():
    tok = create_test_jwt(
        sub="ordinary-student-user",
        roles=["user"],
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def unbound_issuer_headers():
    tok = create_test_jwt(
        sub="unbound-issuer-principal",
        roles=["issuer"],
        issuer_id=None,
    )
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def holder_headers():
    tok = create_test_jwt(
        sub="holder-student-subject",
        roles=["holder"],
    )
    return {"Authorization": f"Bearer {tok}"}



@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    TestClient with get_db overridden to use the isolated test database session.
    """
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()



@pytest.fixture
def fake_chain(monkeypatch):
    """Explicit stateful chain double for API unit tests. Real EVM test is scripts/verify_local_e2e.py."""
    from app.blockchain.client import blockchain_client
    from app.crypto.fingerprint import compute_composite_fingerprint
    records = {}
    counter = [0]
    monkeypatch.setattr(blockchain_client, "can_transact", True)
    monkeypatch.setattr(blockchain_client, "is_connected", lambda *a, **kw: True)
    monkeypatch.setattr(blockchain_client, "is_contract_ready", lambda *a, **kw: True)
    monkeypatch.setattr(blockchain_client, "get_credential_record_on_chain", lambda fingerprint: records.get(fingerprint))
    def result(kwargs):
        counter[0] += 1
        tx_hash = "0x" + format(counter[0], "064x")
        if kwargs.get("on_broadcast"):
            kwargs["on_broadcast"](tx_hash)
        return {"status": "CONFIRMED", "tx_hash": tx_hash, "block_number": counter[0]}
    def issue(**kw):
        fp = compute_composite_fingerprint(kw["doc_digest_hex"], kw["meta_digest_hex"], kw["merkle_root_hex"],
                                           kw["expected_issuer_id"], kw["credential_id_hex"], kw["version"])
        records[fp] = dict(fingerprint=fp, issuer_id=kw["expected_issuer_id"], credential_id=kw["credential_id_hex"],
             document_digest=kw["doc_digest_hex"], metadata_digest=kw["meta_digest_hex"], merkle_root=kw["merkle_root_hex"],
             version=kw["version"], expires_at=kw.get("expires_at", 0), issued_at=1700000000, status="ACTIVE")
        return dict(result(kw), fingerprint=fp, issuer_id=kw["expected_issuer_id"])
    def supersede(**kw):
        old = records[kw.pop("old_fingerprint_hex")]
        res = issue(**kw, credential_id_hex=old["credential_id"], version=old["version"]+1)
        old["status"] = "SUPERSEDED"
        return res
    def lifecycle(target, **kw):
        records[kw["fingerprint_hex"]]["status"] = target
        return result(kw)
    monkeypatch.setattr(blockchain_client, "anchor_credential_fingerprint", issue)
    monkeypatch.setattr(blockchain_client, "supersede_credential_on_chain", supersede)
    monkeypatch.setattr(blockchain_client, "suspend_credential_on_chain", lambda **kw: lifecycle("SUSPENDED", **kw))
    monkeypatch.setattr(blockchain_client, "reactivate_credential_on_chain", lambda **kw: lifecycle("ACTIVE", **kw))
    monkeypatch.setattr(blockchain_client, "revoke_credential_on_chain", lambda **kw: lifecycle("REVOKED", **kw))
    def verify(fingerprint_hex, **kw):
        rec = records.get(fingerprint_hex)
        if not rec:
            return {"is_valid":False,"code":"NOT_FOUND","stored_status":"NONE","is_issuer_active":False,"expires_at":0}
        valid = rec["status"] == "ACTIVE"
        return {"is_valid":valid,"code":"VALID" if valid else "INVALID_STORED_STATUS", "stored_status":rec["status"],
                "is_issuer_active":True,"expires_at":rec["expires_at"]}
    monkeypatch.setattr(blockchain_client, "verify_credential_on_chain", verify)
    return records
