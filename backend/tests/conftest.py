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

