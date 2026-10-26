from fastapi.testclient import TestClient


def test_create_and_get_issuer(client: TestClient, admin_headers):
    issuer_id = "0x" + "11" * 32

    # 1. Create Issuer
    payload = {
        "issuer_id": issuer_id,
        "display_name": "Massachusetts Institute of Technology",
        "metadata_uri": "ipfs://QmTest123",
        "status": "ACTIVE",
    }
    create_res = client.post("/api/v1/issuers", json=payload, headers=admin_headers)
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["issuer_id"] == issuer_id
    assert data["display_name"] == "Massachusetts Institute of Technology"
    assert data["status"] == "ACTIVE"
    assert "on_chain_note" in data

    # 2. Duplicate Issuer ID returns 409 Conflict
    dup_res = client.post("/api/v1/issuers", json=payload, headers=admin_headers)
    assert dup_res.status_code == 409
    assert dup_res.json()["error_code"] == "CONFLICT"

    # 3. Retrieve Issuer
    get_res = client.get(f"/api/v1/issuers/{issuer_id}", headers=admin_headers)
    assert get_res.status_code == 200
    assert get_res.json()["display_name"] == "Massachusetts Institute of Technology"

    # 4. Retrieve Issuer Status
    status_res = client.get(f"/api/v1/issuers/{issuer_id}/status", headers=admin_headers)
    assert status_res.status_code == 200
    assert status_res.json()["db_status"] == "ACTIVE"


def test_issuer_not_found(client: TestClient, admin_headers):
    nonexistent = "0x" + "99" * 32
    res = client.get(f"/api/v1/issuers/{nonexistent}", headers=admin_headers)
    assert res.status_code == 404
    assert res.json()["error_code"] == "NOT_FOUND"


def test_issuer_validation_rejections(client: TestClient, admin_headers):
    # Prohibited Zero Issuer ID
    zero_id = "0x" + "00" * 32
    res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": zero_id, "display_name": "Zero University"},
        headers=admin_headers,
    )
    assert res.status_code == 422
    assert res.json()["error_code"] == "VALIDATION_ERROR"

    # Malformed non-hex string
    res2 = client.post(
        "/api/v1/issuers",
        json={"issuer_id": "invalid-hex", "display_name": "Invalid Uni"},
        headers=admin_headers,
    )
    assert res2.status_code == 422
