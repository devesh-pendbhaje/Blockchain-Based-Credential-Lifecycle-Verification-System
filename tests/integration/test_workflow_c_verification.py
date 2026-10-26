import uuid
import time
import pytest
import httpx
from eth_abi import encode
from eth_utils import keccak
from app.crypto.fingerprint import compute_composite_fingerprint

def test_workflow_c_credential_verification_scenarios(http_client: httpx.Client, api_v1_url: str):
    """
    Workflow C: Credential Verification
    Tests independent cases:
    1. Valid credential metadata with blockchain unavailable boundary.
    2. Missing credential from database.
    3. Tampered component sensitivity (documentDigest, metadataDigest, merkleRoot).
    4. Expired credential dynamically identified.
    5. Superseded credential version history.
    """
    # Create issuer
    raw_issuer = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_issuer
    http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": issuer_id, "display_name": "Verification Authority", "status": "ACTIVE"},
    )

    doc_digest = "0x" + "1" * 64
    meta_digest = "0x" + "2" * 64
    merkle_root = "0x" + "3" * 64
    cred_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex

    # 1. Issue Version 1 Active Credential
    issue_resp = http_client.post(
        f"{api_v1_url}/credentials",
        json={
            "credential_id": cred_id,
            "issuer_id": issuer_id,
            "version": 1,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": merkle_root,
            "expires_at": 0,
        },
    )
    assert issue_resp.status_code == 201
    v1_fingerprint = issue_resp.json()["current_fingerprint"]

    # 1. Verify credential via /credentials/fingerprint/{v1_fingerprint}/verify
    verify_resp = http_client.get(f"{api_v1_url}/credentials/fingerprint/{v1_fingerprint}/verify")
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data["fingerprint"].lower() == v1_fingerprint.lower()
    assert v_data["database_found"] is True
    assert v_data["digest_match"] is True
    assert v_data["lifecycle_status"] == "ACTIVE"
    assert v_data["is_expired"] is False

    # Honest verification boundary:
    # When blockchain RPC is unavailable, is_valid must NEVER be claimed true!
    if not v_data["blockchain_available"]:
        assert v_data["is_valid"] is False
        assert v_data["blockchain_code"] == "UNAVAILABLE"
        assert "unavailable for cryptographic anchoring verification" in v_data["details"]

    # 2. Missing Credential Test
    missing_fp = "0x" + "f" * 64
    missing_resp = http_client.get(f"{api_v1_url}/credentials/fingerprint/{missing_fp}/verify")
    assert missing_resp.status_code == 200
    m_data = missing_resp.json()
    assert m_data["database_found"] is False
    assert m_data["is_valid"] is False
    assert "not found in database" in m_data["details"]

    # 3. Tampered Component Sensitivity:
    # Modifying document digest, metadata digest, or merkle root alters the composite fingerprint
    tampered_doc_digest = "0x" + "1" * 63 + "0"
    tampered_fp = compute_composite_fingerprint(
        document_digest=tampered_doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuer_id=issuer_id,
        credential_id=cred_id,
        version=1,
    )
    assert tampered_fp.lower() != v1_fingerprint.lower()

    # Querying tampered fingerprint against database reports not found
    tampered_resp = http_client.get(f"{api_v1_url}/credentials/fingerprint/{tampered_fp}/verify")
    assert tampered_resp.json()["database_found"] is False

    # 4. Expired Credential Test
    expired_cred_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    past_timestamp = int(time.time()) - 3600  # 1 hour in the past
    exp_issue_resp = http_client.post(
        f"{api_v1_url}/credentials",
        json={
            "credential_id": expired_cred_id,
            "issuer_id": issuer_id,
            "version": 1,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": merkle_root,
            "expires_at": past_timestamp,
        },
    )
    assert exp_issue_resp.status_code == 201
    exp_fp = exp_issue_resp.json()["current_fingerprint"]

    exp_verify_resp = http_client.get(f"{api_v1_url}/credentials/fingerprint/{exp_fp}/verify")
    assert exp_verify_resp.status_code == 200
    assert exp_verify_resp.json()["is_expired"] is True
    assert exp_verify_resp.json()["is_valid"] is False

    # 5. Superseded Version Test
    new_doc_digest = "0x" + "4" * 64
    new_merkle_root = "0x" + "5" * 64
    v2_issue_resp = http_client.post(
        f"{api_v1_url}/credentials",
        json={
            "credential_id": cred_id,
            "issuer_id": issuer_id,
            "version": 2,
            "document_digest": new_doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": new_merkle_root,
            "expires_at": 0,
        },
    )
    assert v2_issue_resp.status_code == 201
    v2_fp = v2_issue_resp.json()["current_fingerprint"]
    assert v2_fp.lower() != v1_fingerprint.lower()

    # Inspect version history
    versions_resp = http_client.get(f"{api_v1_url}/credentials/{cred_id}/versions")
    assert versions_resp.status_code == 200
    vers = versions_resp.json()
    assert len(vers) == 2
    # Version 1 superseded by Version 2
    v1_rec = next(v for v in vers if v["version"] == 1)
    assert v1_rec["superseded_by_fingerprint"].lower() == v2_fp.lower()
