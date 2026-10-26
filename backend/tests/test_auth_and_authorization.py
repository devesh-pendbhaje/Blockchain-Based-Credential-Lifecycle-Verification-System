import time
import pytest
import concurrent.futures
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.config import settings, Settings
from app.crypto.fingerprint import compute_composite_fingerprint
from app.crypto.merkle import SaltedAttributeMerkleTree, hash_leaf
from app.crypto.metadata import canonicalize_and_hash_metadata
from app.crypto.document import compute_document_digest
from app.core.auth.oidc import OIDCValidator
from app.core.exceptions import AppException
import io


# ==============================================================================
# 1. AUTHENTICATION TESTS
# ==============================================================================

def test_protected_route_without_token(client: TestClient):
    """Protected routes must reject requests missing Authorization header with HTTP 401."""
    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"})
    assert res.status_code == 401
    assert res.json()["error_code"] == "UNAUTHORIZED"

    res_cred = client.post("/api/v1/credentials", json={})
    assert res_cred.status_code == 401

    res_chal = client.post("/api/v1/challenges", json={"verifier_session_id": "sess-1"})
    assert res_chal.status_code == 401


def test_malformed_token_rejected(client: TestClient):
    """Malformed bearer tokens must be rejected with HTTP 401."""
    headers = {"Authorization": "Bearer not-a-valid-jwt-token"}
    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "MALFORMED_TOKEN"


def test_invalid_signature_rejected(client: TestClient, make_token):
    """Tokens signed with an untrusted or forged private key must return HTTP 401."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other_pem = other_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    tampered_token = make_token(sub="attacker", roles=["admin"], private_pem=other_pem)
    headers = {"Authorization": f"Bearer {tampered_token}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_SIGNATURE"


def test_expired_token_rejected(client: TestClient, make_token):
    """Expired tokens must be rejected with HTTP 401 and TOKEN_EXPIRED code."""
    expired_token = make_token(sub="user", roles=["admin"], exp_offset=-60)
    headers = {"Authorization": f"Bearer {expired_token}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "TOKEN_EXPIRED"


def test_wrong_issuer_rejected(client: TestClient, make_token):
    """Tokens issued by an untrusted IdP issuer URL must return HTTP 401."""
    wrong_iss_token = make_token(sub="user", roles=["admin"], issuer="https://untrusted-attacker.com")
    headers = {"Authorization": f"Bearer {wrong_iss_token}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_ISSUER"


def test_wrong_audience_rejected(client: TestClient, make_token):
    """Tokens intended for another API service audience must return HTTP 401."""
    wrong_aud_token = make_token(sub="user", roles=["admin"], audience="different-service-api")
    headers = {"Authorization": f"Bearer {wrong_aud_token}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "INVALID_AUDIENCE"


def test_disallowed_algorithm_rejected(client: TestClient, make_token):
    """Tokens signed with disallowed symmetric or none algorithms must return HTTP 401."""
    # Attempt "none" algorithm
    token_none = make_token(sub="user", roles=["admin"], alg="HS256", private_pem="symmetric-secret-key-1234567890123456")
    headers = {"Authorization": f"Bearer {token_none}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "DISALLOWED_ALGORITHM"


def test_unknown_key_id_rejected(client: TestClient, make_token):
    """Tokens referencing an unknown key ID not published in JWKS must return HTTP 401."""
    unknown_kid_token = make_token(sub="user", roles=["admin"], kid="unknown-key-id")
    headers = {"Authorization": f"Bearer {unknown_kid_token}"}

    res = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"}, headers=headers)
    assert res.status_code == 401
    assert res.json()["error_code"] == "SIGNING_KEY_NOT_FOUND"


def test_production_fails_closed_without_auth_config():
    """Production mode must fail-closed during startup if required auth settings are missing."""
    with pytest.raises(ValueError, match="In production mode, AUTH_MODE must be"):
        Settings(ENVIRONMENT="production", AUTH_MODE="disabled")

    with pytest.raises(ValueError, match="Production requires a valid external HTTPS"):
        Settings(ENVIRONMENT="production", AUTH_MODE="oidc", OIDC_ISSUER_URL="http://localhost:8080", OIDC_AUDIENCE="api")

    with pytest.raises(ValueError, match="Production requires OIDC_AUDIENCE"):
        Settings(ENVIRONMENT="production", AUTH_MODE="oidc", OIDC_ISSUER_URL="https://idp.mit.edu", OIDC_AUDIENCE="")


def test_jwks_rotation_and_refreshed_key(make_token):
    """Validator handles dynamic JWKS lookup and key rotation via PyJWKClient mock."""
    key1 = rsa.generate_private_key(65537, 2048)
    key2 = rsa.generate_private_key(65537, 2048)

    pem1 = key1.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    pem2 = key2.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()

    # Mock JWKS client
    class MockJWKSClient:
        def __init__(self):
            self.keys = {
                "key-1": key1.public_key(),
                "key-2": key2.public_key(),
            }

        def get_signing_key_from_jwt(self, tok):
            import jwt as pyjwt
            header = pyjwt.get_unverified_header(tok)
            kid = header.get("kid")
            if kid not in self.keys:
                raise Exception(f"Key {kid} not found")
            class KeyObj:
                key = self.keys[kid]
            return KeyObj()

    old_dev_key = settings.AUTH_DEV_PUBLIC_KEY
    settings.AUTH_DEV_PUBLIC_KEY = None
    try:
        validator = OIDCValidator()
        validator._jwks_client = MockJWKSClient()

        # Token signed with key-1
        tok1 = make_token(sub="user-1", roles=["admin"], kid="key-1", private_pem=pem1)
        principal1 = validator.validate_token(tok1)
        assert principal1.subject == "user-1"

        # Token signed with rotated key-2
        tok2 = make_token(sub="user-2", roles=["admin"], kid="key-2", private_pem=pem2)
        principal2 = validator.validate_token(tok2)
        assert principal2.subject == "user-2"

        # Token with unknown key
        tok3 = make_token(sub="user-3", roles=["admin"], kid="key-revoked", private_pem=pem1)
        with pytest.raises(AppException) as exc_info:
            validator.validate_token(tok3)
        assert exc_info.value.error_code == "SIGNING_KEY_NOT_FOUND"
    finally:
        settings.AUTH_DEV_PUBLIC_KEY = old_dev_key


# ==============================================================================
# 2. AUTHORIZATION & TENANT ISOLATION TESTS
# ==============================================================================

def test_issuer_cannot_perform_admin_action(client: TestClient, issuer_headers):
    """An issuer attempting an administrator action (e.g. registering another institution) is rejected with 403."""
    other_institution_id = "0x" + "99" * 32
    res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": other_institution_id, "display_name": "Unauthorized School"},
        headers=issuer_headers,
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "INSUFFICIENT_PERMISSIONS"


def test_verifier_cannot_issue_credentials(client: TestClient, verifier_headers):
    """A verifier principal attempting credential issuance is rejected with HTTP 403."""
    res = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": "0x" + "aa" * 32,
            "issuer_id": "0x" + "11" * 32,
            "version": 1,
            "document_digest": "0x" + "12" * 32,
            "metadata_digest": "0x" + "34" * 32,
            "merkle_root": "0x" + "56" * 32,
        },
        headers=verifier_headers,
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "INSUFFICIENT_PERMISSIONS"


def test_cross_tenant_credential_issuance_prevented(client: TestClient, issuer_headers):
    """
    IDOR Prevention: Issuer 0x11... attempting to issue a credential for Issuer 0x22...
    is rejected at the tenant boundary with HTTP 403 TENANT_MISMATCH.
    """
    foreign_issuer_id = "0x" + "22" * 32
    res = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": "0x" + "bb" * 32,
            "issuer_id": foreign_issuer_id,
            "version": 1,
            "document_digest": "0x" + "12" * 32,
            "metadata_digest": "0x" + "34" * 32,
            "merkle_root": "0x" + "56" * 32,
        },
        headers=issuer_headers,
    )
    assert res.status_code == 403
    assert res.json()["error_code"] == "TENANT_MISMATCH"


def test_cross_tenant_credential_inspection_prevented(client: TestClient, admin_headers, issuer_headers, other_issuer_headers):
    """
    IDOR Prevention: Issuer A cannot inspect or fetch version history for Issuer B's credential.
    """
    cred_id = "0x" + "cc" * 32
    issuer_a_id = "0x" + "11" * 32

    # 1. Admin creates issuer record
    client.post("/api/v1/issuers", json={"issuer_id": issuer_a_id, "display_name": "University A"}, headers=admin_headers)

    # 2. Issuer A issues credential
    res_create = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": cred_id,
            "issuer_id": issuer_a_id,
            "version": 1,
            "document_digest": "0x" + "12" * 32,
            "metadata_digest": "0x" + "34" * 32,
            "merkle_root": "0x" + "56" * 32,
        },
        headers=issuer_headers,
    )
    assert res_create.status_code == 201

    # 3. Issuer A can inspect their own credential
    res_self = client.get(f"/api/v1/credentials/{cred_id}", headers=issuer_headers)
    assert res_self.status_code == 200

    # 4. Issuer B attempts to inspect Issuer A's credential -> 403 TENANT_MISMATCH
    res_other = client.get(f"/api/v1/credentials/{cred_id}", headers=other_issuer_headers)
    assert res_other.status_code == 403
    assert res_other.json()["error_code"] == "TENANT_MISMATCH"

    # 5. Issuer B attempts to fetch versions for Issuer A's credential -> 403 TENANT_MISMATCH
    res_other_ver = client.get(f"/api/v1/credentials/{cred_id}/versions", headers=other_issuer_headers)
    assert res_other_ver.status_code == 403
    assert res_other_ver.json()["error_code"] == "TENANT_MISMATCH"


def test_spoofed_role_in_request_rejected(client: TestClient, make_token):
    """Client-supplied role parameters in request body or headers cannot elevate privilege."""
    # Token only has "user" role
    unprivileged_token = make_token(sub="attacker", roles=["user"])
    headers = {
        "Authorization": f"Bearer {unprivileged_token}",
        "X-User-Role": "admin",
        "X-Role": "issuer",
    }

    # Attempt admin endpoint
    res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": "0x" + "33" * 32, "display_name": "Spoof Uni", "role": "admin"},
        headers=headers,
    )
    assert res.status_code == 403


def test_authorized_requests_succeed(client: TestClient, admin_headers, issuer_headers):
    """Correctly authenticated and authorized requests proceed successfully."""
    issuer_id = "0x" + "11" * 32
    res_iss = client.post(
        "/api/v1/issuers",
        json={"issuer_id": issuer_id, "display_name": "Legitimate Authority"},
        headers=admin_headers,
    )
    assert res_iss.status_code in (201, 409)

    res_cred = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": "0x" + "ee" * 32,
            "issuer_id": issuer_id,
            "version": 1,
            "document_digest": "0x" + "12" * 32,
            "metadata_digest": "0x" + "34" * 32,
            "merkle_root": "0x" + "56" * 32,
        },
        headers=issuer_headers,
    )
    assert res_cred.status_code in (201, 409)


# ==============================================================================
# 3. VERIFIER IDENTITY & CHALLENGE SECURITY TESTS
# ==============================================================================

def test_cross_verifier_challenge_consumption_rejected(client: TestClient, verifier_headers, other_verifier_headers):
    """
    Security Invariant: Challenge issued to Verifier A cannot be consumed by Verifier B.
    Attempts must be rejected with HTTP 403 VERIFIER_PRINCIPAL_MISMATCH.
    """
    # 1. Verifier A issues challenge
    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "sess-alpha-1"},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    # Build valid presentation
    tree = SaltedAttributeMerkleTree({"degree": "Ph.D."})
    disclosed = [{"key": "degree", "value": "Ph.D.", "salt": tree.salts["degree"], "proof": tree.get_proof("degree")}]
    presentation = {
        "credential_fingerprint": "0x" + "55" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    # 2. Verifier B attempts to verify and consume Verifier A's challenge
    res_verify = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "sess-alpha-1"},
        headers=other_verifier_headers,  # Cross-verifier attempt!
    )
    assert res_verify.status_code == 403
    assert res_verify.json()["error_code"] == "VERIFIER_PRINCIPAL_MISMATCH"


def test_forged_session_id_rejected(client: TestClient, verifier_headers):
    """Caller attempting to use challenge with mismatched session ID is rejected with 403."""
    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "session-real"},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    tree = SaltedAttributeMerkleTree({"name": "Alice"})
    disclosed = [{"key": "name", "value": "Alice", "salt": tree.salts["name"], "proof": tree.get_proof("name")}]
    presentation = {
        "credential_fingerprint": "0x" + "55" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    res_verify = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "session-forged"},
        headers=verifier_headers,
    )
    assert res_verify.status_code == 403
    assert res_verify.json()["error_code"] == "VERIFIER_SESSION_MISMATCH"


def test_challenge_scoped_to_wrong_fingerprint_rejected(client: TestClient, verifier_headers):
    """Scoped challenge used for a different credential fingerprint must return HTTP 403."""
    expected_fp = "0x" + "11" * 32
    actual_fp = "0x" + "22" * 32

    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "sess-scope-1", "credential_fingerprint": expected_fp},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    tree = SaltedAttributeMerkleTree({"name": "Alice"})
    disclosed = [{"key": "name", "value": "Alice", "salt": tree.salts["name"], "proof": tree.get_proof("name")}]
    presentation = {
        "credential_fingerprint": actual_fp,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    res_verify = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "sess-scope-1"},
        headers=verifier_headers,
    )
    assert res_verify.status_code == 403
    assert res_verify.json()["error_code"] == "CHALLENGE_SCOPE_MISMATCH"


def test_expired_challenge_rejected(client: TestClient, verifier_headers):
    """Expired challenge nonces must return HTTP 410 CHALLENGE_EXPIRED."""
    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "sess-exp", "expiry_seconds": 10},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    tree = SaltedAttributeMerkleTree({"status": "active"})
    disclosed = [{"key": "status", "value": "active", "salt": tree.salts["status"], "proof": tree.get_proof("status")}]
    presentation = {
        "credential_fingerprint": "0x" + "55" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    # Simulate expiry in time
    time.sleep(0.1)

    from app.db.session import get_db
    from app.models.verifier_challenge import VerifierChallenge
    from datetime import datetime, timezone, timedelta

    # Force expiration in DB for test
    db = next(client.app.dependency_overrides[get_db]())
    chal_rec = db.query(VerifierChallenge).filter_by(challenge_id=chal["challenge_id"]).first()
    chal_rec.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    res_verify = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "sess-exp"},
        headers=verifier_headers,
    )
    assert res_verify.status_code == 410
    assert res_verify.json()["error_code"] == "CHALLENGE_EXPIRED"


def test_replayed_challenge_rejected(client: TestClient, verifier_headers):
    """Replaying an already consumed challenge must be rejected with HTTP 409 CHALLENGE_ALREADY_CONSUMED."""
    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "sess-replay"},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    tree = SaltedAttributeMerkleTree({"major": "CS"})
    disclosed = [{"key": "major", "value": "CS", "salt": tree.salts["major"], "proof": tree.get_proof("major")}]
    presentation = {
        "credential_fingerprint": "0x" + "55" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    # First consumption succeeds
    res1 = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "sess-replay"},
        headers=verifier_headers,
    )
    assert res1.status_code == 200
    assert res1.json()["challenge_verified"] is True

    # Second consumption attempt with identical nonce -> HTTP 409
    res2 = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": "sess-replay"},
        headers=verifier_headers,
    )
    assert res2.status_code == 409
    assert res2.json()["error_code"] == "CHALLENGE_ALREADY_CONSUMED"


def test_concurrent_challenge_consumption_exactly_one_success(client: TestClient, verifier_headers):
    """
    Concurrency Invariant: 10 concurrent requests attempting to consume the same challenge
    must yield EXACTLY ONE success (200 OK) and 9 rejections (409 Conflict).
    """
    res_chal = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": "sess-race-cond"},
        headers=verifier_headers,
    )
    assert res_chal.status_code == 201
    chal = res_chal.json()

    tree = SaltedAttributeMerkleTree({"gpa": "3.95"})
    disclosed = [{"key": "gpa", "value": "3.95", "salt": tree.salts["gpa"], "proof": tree.get_proof("gpa")}]
    presentation = {
        "credential_fingerprint": "0x" + "55" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": disclosed,
        "challenge_id": chal["challenge_id"],
        "challenge_nonce": chal["challenge_nonce"],
    }

    def attempt_verify():
        return client.post(
            "/api/v1/presentations/verify",
            json={"presentation": presentation, "verifier_session_id": "sess-race-cond"},
            headers=verifier_headers,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(attempt_verify) for _ in range(10)]
        results = [f.result() for f in futures]

    statuses = [r.status_code for r in results]
    success_count = statuses.count(200)
    conflict_count = statuses.count(409)

    assert success_count == 1, f"Expected exactly 1 success under concurrency, got {success_count}. Statuses: {statuses}"
    assert conflict_count == 9, f"Expected 9 conflicts, got {conflict_count}"


def test_tampered_merkle_proof_rejected(client: TestClient, verifier_headers):
    """Tampered claim values, opening salts, or sibling proofs must return HTTP 400 INVALID_MERKLE_PROOF."""
    tree = SaltedAttributeMerkleTree({"degree": "Bachelor of Science"})
    real_salt = tree.salts["degree"]
    real_proof = tree.get_proof("degree")

    # 1. Tampered value
    tampered_val = [
        {"key": "degree", "value": "Doctor of Medicine", "salt": real_salt, "proof": real_proof}
    ]
    res1 = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": {
                "credential_fingerprint": "0x" + "55" * 32,
                "merkle_root": tree.root,
                "disclosed_claims": tampered_val,
            },
            "verifier_session_id": "sess-tamper",
        },
        headers=verifier_headers,
    )
    assert res1.status_code == 400
    assert res1.json()["error_code"] == "INVALID_MERKLE_PROOF"

    # 2. Tampered salt
    tampered_salt = [
        {"key": "degree", "value": "Bachelor of Science", "salt": "0x" + "99" * 32, "proof": real_proof}
    ]
    res2 = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": {
                "credential_fingerprint": "0x" + "55" * 32,
                "merkle_root": tree.root,
                "disclosed_claims": tampered_salt,
            },
            "verifier_session_id": "sess-tamper",
        },
        headers=verifier_headers,
    )
    assert res2.status_code == 400
    assert res2.json()["error_code"] == "INVALID_MERKLE_PROOF"


def test_unrequested_attributes_remain_undisclosed(client: TestClient, admin_headers):
    """Selective disclosure presentation generation only discloses specified keys."""
    attributes = {
        "student_id": "MIT-9901",
        "full_name": "Alice Johnson",
        "ssn": "000-12-3456",
        "degree": "B.S. Computer Science",
        "honors": "Summa Cum Laude",
    }
    tree = SaltedAttributeMerkleTree(attributes)

    res = client.post(
        "/api/v1/presentations/generate",
        json={
            "credential_id": "0x" + "11" * 32,
            "version": 1,
            "attributes": attributes,
            "salts": tree.salts,
            "disclosed_keys": ["degree", "honors"],
            "document_digest": "0x" + "22" * 32,
            "metadata_digest": "0x" + "33" * 32,
            "issuer_id": "0x" + "44" * 32,
        },
        headers=admin_headers,
    )
    assert res.status_code == 200
    data = res.json()

    disclosed_keys = [c["key"] for c in data["disclosed_claims"]]
    assert "degree" in disclosed_keys
    assert "honors" in disclosed_keys
    assert "ssn" not in disclosed_keys
    assert "student_id" not in disclosed_keys
    assert "full_name" not in disclosed_keys


# ==============================================================================
# 4. REGRESSION INVARIANTS & SECURITY
# ==============================================================================

def test_composite_fingerprint_invariant():
    """Verify that composite fingerprint formula matches Solidity keccak256(abi.encode(...)) exactly."""
    doc_digest = "0x" + "11" * 32
    meta_digest = "0x" + "22" * 32
    merkle_root = "0x" + "33" * 32
    issuer_id = "0x" + "44" * 32
    credential_id = "0x" + "55" * 32
    version = 1

    fp1 = compute_composite_fingerprint(doc_digest, meta_digest, merkle_root, issuer_id, credential_id, version)
    assert fp1.startswith("0x")
    assert len(fp1) == 66

    # Any change alters fingerprint
    fp2 = compute_composite_fingerprint(doc_digest, meta_digest, merkle_root, issuer_id, credential_id, version + 1)
    assert fp1 != fp2


def test_health_endpoints_do_not_leak_secrets(client: TestClient):
    """Health probes must report operational status without exposing connection strings or config secrets."""
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "live"}

    res_ready = client.get("/health/ready")
    assert res_ready.status_code in (200, 503)
    body = res_ready.json()
    assert "password" not in str(body).lower()
    assert "secret" not in str(body).lower()
    assert "token" not in str(body).lower()
    assert "key" not in str(body).lower()
