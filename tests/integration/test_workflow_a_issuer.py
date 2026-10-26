import uuid
import pytest
import httpx

def test_workflow_a_issuer_lifecycle(http_client: httpx.Client, api_v1_url: str):
    """
    Workflow A: Issuer Registration
    1. Register an issuer using supported API.
    2. Retrieve the issuer record.
    3. Confirm returned status.
    4. Attempt duplicate registration.
    5. Verify duplicate is rejected correctly (409 Conflict).
    6. Determine whether issuer registration is database-only or also registered on-chain.
    7. Verify status endpoint communicates database vs on-chain distinction.
    """
    # Generate unique 32-byte hex issuer ID
    raw_id = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_id
    display_name = f"Integration Test University - {uuid.uuid4().hex[:8]}"
    metadata_uri = f"https://example.edu/issuers/{raw_id[:8]}.json"

    # 1. Register issuer
    create_payload = {
        "issuer_id": issuer_id,
        "display_name": display_name,
        "metadata_uri": metadata_uri,
        "status": "ACTIVE",
    }
    create_resp = http_client.post(f"{api_v1_url}/issuers", json=create_payload)
    assert create_resp.status_code == 201, f"Failed to register issuer: {create_resp.text}"
    created_data = create_resp.json()
    assert created_data["issuer_id"].lower() == issuer_id.lower()
    assert created_data["display_name"] == display_name
    assert created_data["status"] == "ACTIVE"

    # 2. Retrieve issuer record
    get_resp = http_client.get(f"{api_v1_url}/issuers/{issuer_id}")
    assert get_resp.status_code == 200
    retrieved_data = get_resp.json()
    assert retrieved_data["issuer_id"].lower() == issuer_id.lower()
    assert retrieved_data["display_name"] == display_name
    assert retrieved_data["status"] == "ACTIVE"

    # 3. Confirm returned status and timestamps
    assert "created_at" in retrieved_data
    assert "updated_at" in retrieved_data

    # 4 & 5. Attempt duplicate registration -> must reject with 409
    dup_resp = http_client.post(f"{api_v1_url}/issuers", json=create_payload)
    assert dup_resp.status_code == 409, f"Expected 409 Conflict on duplicate, got {dup_resp.status_code}"
    dup_err = dup_resp.json()
    assert dup_err["error_code"] in ["CONFLICT", "ISSUER_ALREADY_EXISTS", "ENTITY_CONFLICT"]

    # 6 & 7. Check database vs on-chain status endpoint
    status_resp = http_client.get(f"{api_v1_url}/issuers/{issuer_id}/status")
    assert status_resp.status_code == 200
    st_data = status_resp.json()
    assert st_data["issuer_id"].lower() == issuer_id.lower()
    assert st_data["db_status"] == "ACTIVE"
    # When no blockchain node is connected or contract not registered, on_chain_status is UNAVAILABLE/NONE
    assert st_data["is_on_chain_active"] is False or st_data["on_chain_status"] in ["UNAVAILABLE", "NONE", "NOT_FOUND"]


def test_workflow_a_issuer_validation_boundaries(http_client: httpx.Client, api_v1_url: str):
    """Test validation boundaries: zero bytes32 and invalid hex lengths."""
    # Zero bytes32 prohibited
    zero_id = "0x" + "0" * 64
    zero_resp = http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": zero_id, "display_name": "Zero Issuer", "status": "ACTIVE"},
    )
    assert zero_resp.status_code == 422

    # Malformed length (63 characters instead of 66)
    short_id = "0x" + "a" * 61
    short_resp = http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": short_id, "display_name": "Short Issuer", "status": "ACTIVE"},
    )
    assert short_resp.status_code == 422
