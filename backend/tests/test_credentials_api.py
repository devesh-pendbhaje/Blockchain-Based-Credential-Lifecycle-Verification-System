from fastapi.testclient import TestClient
from app.crypto.fingerprint import compute_composite_fingerprint


def _setup_issuer(client: TestClient, issuer_id: str, headers: dict):
    client.post(
        "/api/v1/issuers",
        json={"issuer_id": issuer_id, "display_name": "Stanford University", "status": "ACTIVE"},
        headers=headers,
    )


def test_credential_lifecycle_and_versioning(client: TestClient, admin_headers):
    issuer_id = "0x" + "11" * 32
    credential_id = "0x" + "22" * 32
    doc1 = "0x" + "33" * 32
    meta1 = "0x" + "44" * 32
    root1 = "0x" + "55" * 32

    _setup_issuer(client, issuer_id, admin_headers)

    # 1. Issue Version 1
    fp1 = compute_composite_fingerprint(doc1, meta1, root1, issuer_id, credential_id, 1)
    res = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "document_digest": doc1,
            "metadata_digest": meta1,
            "merkle_root": root1,
            "version": 1,
            "expires_at": 0,
        },
        headers=admin_headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["credential_id"] == credential_id
    assert data["current_version"] == 1
    assert data["current_fingerprint"] == fp1

    # 2. Retrieve Credential
    get_res = client.get(f"/api/v1/credentials/{credential_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["current_fingerprint"] == fp1

    # 3. Supersede to Version 2
    doc2 = "0x" + "66" * 32
    meta2 = "0x" + "77" * 32
    root2 = "0x" + "88" * 32
    fp2 = compute_composite_fingerprint(doc2, meta2, root2, issuer_id, credential_id, 2)

    res_v2 = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "document_digest": doc2,
            "metadata_digest": meta2,
            "merkle_root": root2,
            "version": 2,
            "expires_at": 0,
        },
        headers=admin_headers,
    )
    assert res_v2.status_code == 201
    assert res_v2.json()["current_version"] == 2
    assert res_v2.json()["current_fingerprint"] == fp2

    # 4. Non-sequential version jump (e.g. requesting v4) fails
    res_v4 = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "document_digest": doc2,
            "metadata_digest": meta2,
            "merkle_root": root2,
            "version": 4,
            "expires_at": 0,
        },
        headers=admin_headers,
    )
    assert res_v4.status_code == 400
    assert res_v4.json()["error_code"] == "INVALID_VERSION_SEQUENCE"

    # 5. Retrieve Version History
    versions_res = client.get(f"/api/v1/credentials/{credential_id}/versions", headers=admin_headers)
    assert versions_res.status_code == 200
    versions = versions_res.json()
    assert len(versions) == 2
    assert versions[0]["version"] == 1
    assert versions[0]["fingerprint"] == fp1
    assert versions[0]["superseded_by_fingerprint"] == fp2
    assert versions[1]["version"] == 2
    assert versions[1]["fingerprint"] == fp2


def test_credential_verification_endpoint(client: TestClient, admin_headers):
    issuer_id = "0x" + "ab" * 32
    credential_id = "0x" + "cd" * 32
    doc1 = "0x" + "01" * 32
    meta1 = "0x" + "02" * 32
    root1 = "0x" + "03" * 32

    _setup_issuer(client, issuer_id, admin_headers)

    fp = compute_composite_fingerprint(doc1, meta1, root1, issuer_id, credential_id, 1)
    client.post(
        "/api/v1/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "document_digest": doc1,
            "metadata_digest": meta1,
            "merkle_root": root1,
            "version": 1,
            "expires_at": 0,
        },
        headers=admin_headers,
    )

    # 1. Anonymous Public Verification Query (No Authorization header)
    res_anon = client.get(f"/api/v1/credentials/fingerprint/{fp}/verify")
    assert res_anon.status_code == 200
    data_anon = res_anon.json()
    assert data_anon["fingerprint"] == fp
    assert data_anon["database_found"] is True
    # Ensure zero leak of internal secrets, raw digests, or tenant identifiers
    for forbidden_field in ("document_digest", "metadata_digest", "merkle_root", "salts", "credential_id", "issuer_id", "idempotency_key"):
        assert forbidden_field not in data_anon

    # When blockchain RPC is connected or offline, must report truthfully and NOT fabricate valid: true
    if not data_anon["blockchain_available"]:
        assert "blockchain network or contract is unavailable" in data_anon["details"]
    else:
        assert data_anon["blockchain_code"] == "NOT_FOUND"
    assert data_anon["is_valid"] is False
    assert data_anon["digest_match"] is True
    assert data_anon["is_expired"] is False

    # 2. Authenticated Verification Query (Caller with Bearer token can also query)
    res_auth = client.get(f"/api/v1/credentials/fingerprint/{fp}/verify", headers=admin_headers)
    assert res_auth.status_code == 200
    assert res_auth.json()["fingerprint"] == fp


def test_verification_unregistered_fingerprint(client: TestClient):
    # Anonymous query with unmapped random fingerprint returns 200 with database_found=False
    random_fp = "0x" + "ef" * 32
    res = client.get(f"/api/v1/credentials/fingerprint/{random_fp}/verify")
    assert res.status_code == 200
    data = res.json()
    assert data["database_found"] is False
    assert data["is_valid"] is False


def test_public_verification_anonymous_and_sensitive_endpoints_protected(client: TestClient, admin_headers):
    """
    Regression test ensuring:
    1. Read-only credential verification by fingerprint is publicly accessible without authentication.
    2. All sensitive administrative, issuance, lifecycle, and document operations remain strictly protected with HTTP 401.
    """
    issuer_id = "0x" + "a1" * 32
    credential_id = "0x" + "b2" * 32
    doc_digest = "0x" + "c3" * 32
    meta_digest = "0x" + "d4" * 32
    merkle_root = "0x" + "e5" * 32

    _setup_issuer(client, issuer_id, admin_headers)

    fp = compute_composite_fingerprint(doc_digest, meta_digest, merkle_root, issuer_id, credential_id, 1)
    create_res = client.post(
        "/api/v1/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": merkle_root,
            "version": 1,
            "expires_at": 0,
        },
        headers=admin_headers,
    )
    assert create_res.status_code == 201

    # Public verification MUST succeed without any token
    verify_res = client.get(f"/api/v1/credentials/fingerprint/{fp}/verify")
    assert verify_res.status_code == 200
    assert verify_res.json()["database_found"] is True

    # Sensitive endpoints MUST be rejected with HTTP 401 when called anonymously
    unauth_endpoints = [
        ("POST", "/api/v1/credentials", {"credential_id": credential_id}),
        ("GET", f"/api/v1/credentials/{credential_id}", None),
        ("GET", f"/api/v1/credentials/{credential_id}/versions", None),
        ("GET", f"/api/v1/credentials/fingerprint/{fp}", None),
        ("POST", f"/api/v1/credentials/{credential_id}/versions/1/anchor", {}),
        ("POST", "/api/v1/issuers", {"issuer_id": "0x" + "99" * 32, "display_name": "Test"}),
        ("GET", f"/api/v1/issuers/{issuer_id}", None),
        ("POST", f"/api/v1/issuers/{issuer_id}/register-on-chain", {"signing_address": "0x1111111111111111111111111111111111111111"}),
        ("POST", "/api/v1/challenges", {"verifier_session_id": "sess-test"}),
        ("POST", "/api/v1/presentations/generate", {"credential_id": credential_id}),
        ("POST", "/api/v1/presentations/verify", {"presentation": {}}),
    ]

    for method, path, json_body in unauth_endpoints:
        if method == "POST":
            res = client.post(path, json=json_body)
        else:
            res = client.get(path)
        assert res.status_code == 401, f"Expected 401 for unauthenticated {method} {path}, got {res.status_code}"
        assert res.json().get("error_code") == "UNAUTHORIZED"


def test_idempotency_key_enforcement(client: TestClient, admin_headers):
    issuer_id = "0x" + "aa" * 32
    cred_id = "0x" + "bb" * 32
    doc1 = "0x" + "11" * 32
    meta1 = "0x" + "22" * 32
    root1 = "0x" + "33" * 32
    idempotency_key = "idemp-key-alpha-99"

    _setup_issuer(client, issuer_id, admin_headers)

    payload = {
        "credential_id": cred_id,
        "issuer_id": issuer_id,
        "document_digest": doc1,
        "metadata_digest": meta1,
        "merkle_root": root1,
        "version": 1,
        "expires_at": 0,
        "idempotency_key": idempotency_key,
    }

    # 1. First submission succeeds (status is PENDING if blockchain is offline, or FAILED if unaccredited on-chain)
    res1 = client.post("/api/v1/credentials", json=payload, headers=admin_headers)
    assert res1.status_code == 201
    assert res1.json()["issuance_status"] in ("PENDING", "FAILED", "CONFIRMED")

    # 2. Identical retry with exact same key and payload returns identical record
    res2 = client.post("/api/v1/credentials", json=payload, headers=admin_headers)
    assert res2.status_code in (200, 201)
    assert res2.json()["credential_id"] == cred_id
    assert res2.json()["current_fingerprint"] == res1.json()["current_fingerprint"]
    assert res2.json()["issuance_status"] == res1.json()["issuance_status"]

    # 3. Reusing the same idempotency key for a DIFFERENT request is strictly rejected with 409 Conflict
    diff_payload = {
        "credential_id": "0x" + "cc" * 32,  # Different credential
        "issuer_id": issuer_id,
        "document_digest": doc1,
        "metadata_digest": meta1,
        "merkle_root": root1,
        "version": 1,
        "expires_at": 0,
        "idempotency_key": idempotency_key,  # Reused key
    }
    res3 = client.post("/api/v1/credentials", json=diff_payload, headers=admin_headers)
    assert res3.status_code == 409
    assert res3.json()["error_code"] == "CONFLICT"
    assert "already been used for a different credential" in res3.json()["message"]


def test_list_credentials(client: TestClient, admin_headers):
    issuer_id = "0x" + "a1" * 32
    cred_id = "0x" + "b1" * 32
    doc = "0x" + "c1" * 32
    meta = "0x" + "d1" * 32
    root = "0x" + "e1" * 32

    _setup_issuer(client, issuer_id, admin_headers)
    client.post(
        "/api/v1/credentials",
        json={
            "credential_id": cred_id,
            "issuer_id": issuer_id,
            "document_digest": doc,
            "metadata_digest": meta,
            "merkle_root": root,
            "version": 1,
            "expires_at": 0,
        },
        headers=admin_headers,
    )

    res = client.get("/api/v1/credentials", headers=admin_headers)
    assert res.status_code == 200
    creds = res.json()
    assert isinstance(creds, list)
    matching = [c for c in creds if c["credential_id"] == cred_id]
    assert len(matching) == 1
    assert matching[0]["current_version"] == 1

