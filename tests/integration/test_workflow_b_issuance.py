import uuid
import hashlib
import json
import pytest
import httpx
from eth_abi import encode
from eth_utils import keccak
from app.crypto.merkle import SaltedAttributeMerkleTree

def test_workflow_b_credential_issuance_full_lifecycle(http_client: httpx.Client, api_v1_url: str):
    """
    Workflow B: Credential Issuance End-to-End
    1. Prepare test certificate (no real PII).
    2. Upload through /documents/upload.
    3. Confirm document digest matches raw bytes SHA-256.
    4. Verify off-chain encrypted storage metadata.
    5. Submit metadata to /documents/canonical-metadata (RFC 8785).
    6. Build salted Merkle tree.
    7. Submit credential issuance request.
    8. Retrieve resulting credential and version.
    9. Independently recompute 6-component composite fingerprint and verify exact match.
    10. Enforce version monotonicity.
    """
    # 1. Register an active issuer for this credential
    raw_issuer = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_issuer
    issuer_resp = http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": issuer_id, "display_name": "Test Accredited Authority", "status": "ACTIVE"},
    )
    assert issuer_resp.status_code == 201

    # 2. Prepare test certificate bytes (synthetic test certificate with zero PII)
    test_cert_content = b"%PDF-1.4\n% Synthetic Test Credential Certificate for Integration Testing\nIssuer: Test Accredited Authority\nStatus: Unofficial Sample\nEOF"
    expected_doc_digest = "0x" + hashlib.sha256(test_cert_content).hexdigest().lower()

    # Upload via /documents/upload
    files = {"file": ("test_cert.pdf", test_cert_content, "application/pdf")}
    upload_resp = http_client.post(f"{api_v1_url}/documents/upload", files=files)
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
    upload_data = upload_resp.json()

    # 3. Confirm document digest matches original bytes
    assert upload_data["document_digest"].lower() == expected_doc_digest.lower()
    storage_id = upload_data["storage_id"]
    assert storage_id

    # 4. Verify storage metadata endpoint (does NOT leak plaintext)
    meta_resp = http_client.get(f"{api_v1_url}/documents/{storage_id}/metadata")
    assert meta_resp.status_code == 200
    meta_data = meta_resp.json()
    assert meta_data["storage_id"] == storage_id
    assert meta_data["document_digest"].lower() == expected_doc_digest.lower()
    assert meta_data["byte_size"] == len(test_cert_content)

    # 5. RFC 8785 Metadata Canonicalization
    raw_metadata = {
        "degree": "Bachelor of Science in Computer Science",
        "honors": "Cum Laude",
        "academic_year": "2025-2026",
        "institution": "University of Decentralized Systems",
    }
    canon_resp = http_client.post(
        f"{api_v1_url}/documents/canonical-metadata",
        json={"metadata": raw_metadata},
    )
    assert canon_resp.status_code == 200
    canon_data = canon_resp.json()
    metadata_digest = canon_data["metadata_digest"]
    assert metadata_digest.startswith("0x")
    assert len(metadata_digest) == 66

    # 6. Build Salted Merkle Tree
    attributes = {
        "degree": "Bachelor of Science in Computer Science",
        "major": "Computer Science",
        "gpa": "3.85",
        "graduation_date": "2026-06-15",
    }
    tree = SaltedAttributeMerkleTree(attributes)
    merkle_root = tree.root
    assert merkle_root.startswith("0x")
    assert len(merkle_root) == 66

    # 7. Submit Credential Issuance Request
    raw_cred = uuid.uuid4().hex + uuid.uuid4().hex
    credential_id = "0x" + raw_cred
    idempotency_key = f"idem-key-{uuid.uuid4().hex}"

    issuance_payload = {
        "credential_id": credential_id,
        "issuer_id": issuer_id,
        "version": 1,
        "document_digest": expected_doc_digest,
        "metadata_digest": metadata_digest,
        "merkle_root": merkle_root,
        "idempotency_key": idempotency_key,
        "expires_at": 0,
    }

    issue_resp = http_client.post(f"{api_v1_url}/credentials", json=issuance_payload)
    assert issue_resp.status_code == 201, f"Issuance failed: {issue_resp.text}"
    issue_data = issue_resp.json()
    assert issue_data["credential_id"].lower() == credential_id.lower()
    assert issue_data["current_version"] == 1
    assert issue_data["current_status"] == "ACTIVE"
    returned_fingerprint = issue_data["current_fingerprint"]

    # 8. Retrieve Credential & Versions
    get_cred_resp = http_client.get(f"{api_v1_url}/credentials/{credential_id}")
    assert get_cred_resp.status_code == 200
    assert get_cred_resp.json()["current_fingerprint"].lower() == returned_fingerprint.lower()

    get_vers_resp = http_client.get(f"{api_v1_url}/credentials/{credential_id}/versions")
    assert get_vers_resp.status_code == 200
    versions = get_vers_resp.json()
    assert len(versions) == 1
    assert versions[0]["version"] == 1
    assert versions[0]["fingerprint"].lower() == returned_fingerprint.lower()

    # 9. Independently Recompute the 6-component composite fingerprint:
    # keccak256(abi.encode(documentDigest, metadataDigest, merkleRoot, issuerId, credentialId, version))
    doc_b = bytes.fromhex(expected_doc_digest[2:])
    meta_b = bytes.fromhex(metadata_digest[2:])
    root_b = bytes.fromhex(merkle_root[2:])
    issuer_b = bytes.fromhex(issuer_id[2:])
    cred_b = bytes.fromhex(credential_id[2:])
    version_uint32 = 1

    encoded_tuple = encode(
        ["bytes32", "bytes32", "bytes32", "bytes32", "bytes32", "uint32"],
        [doc_b, meta_b, root_b, issuer_b, cred_b, version_uint32],
    )
    independent_fp = "0x" + keccak(encoded_tuple).hex()
    assert independent_fp.lower() == returned_fingerprint.lower(), (
        f"Composite fingerprint mismatch!\nComputed: {independent_fp}\nReturned: {returned_fingerprint}"
    )

    # 10. Test Idempotency with exact same request
    idem_resp = http_client.post(f"{api_v1_url}/credentials", json=issuance_payload)
    assert idem_resp.status_code == 201 or idem_resp.status_code == 200
    assert idem_resp.json()["current_fingerprint"].lower() == returned_fingerprint.lower()

    # 11. Test Monotonicity: Non-sequential version 3 before version 2 must be rejected with 400
    invalid_seq_payload = dict(issuance_payload)
    invalid_seq_payload["version"] = 3
    invalid_seq_payload["idempotency_key"] = f"idem-key-{uuid.uuid4().hex}"
    invalid_seq_resp = http_client.post(f"{api_v1_url}/credentials", json=invalid_seq_payload)
    assert invalid_seq_resp.status_code == 400
    assert invalid_seq_resp.json()["error_code"] == "INVALID_VERSION_SEQUENCE"
