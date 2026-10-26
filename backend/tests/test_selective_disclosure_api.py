import io
import pytest
from app.crypto.fingerprint import compute_composite_fingerprint


def test_full_selective_disclosure_and_challenge_flow(client, admin_headers, verifier_headers):
    """
    End-to-end integration test:
    1. Upload certificate document -> SHA-256 digest.
    2. Canonicalize metadata JSON -> Keccak-256 metadataDigest.
    3. Build salted Merkle tree -> Merkle root.
    4. Issue verifier challenge.
    5. Generate presentation revealing only selected attributes (disclosing degree, hiding ssn).
    6. Verify presentation:
       - Success on first submission.
       - Rejection on replay submission.
    """
    # 1. Document upload
    pdf_bytes = b"%PDF-1.4\n%Academic Certificate for Bob\n%%EOF"
    upload_resp = client.post(
        "/api/v1/documents/upload",
        files={"file": ("cert.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
        headers=admin_headers,
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    storage_id = upload_data["storage_id"]
    doc_digest = upload_data["document_digest"]

    # 2. Inspect metadata without leaking content
    meta_resp = client.get(f"/api/v1/documents/{storage_id}/metadata", headers=admin_headers)
    assert meta_resp.status_code == 200
    assert meta_resp.json()["document_digest"] == doc_digest

    # 3. Canonical metadata
    metadata_obj = {"student_name": "Bob Jones", "grad_year": 2026}
    canon_resp = client.post(
        "/api/v1/documents/canonical-metadata",
        json={"metadata": metadata_obj},
        headers=admin_headers,
    )
    assert canon_resp.status_code == 200
    meta_digest = canon_resp.json()["metadata_digest"]

    # 4. Merkle tree construction
    attributes = {
        "degree": "B.S. Software Engineering",
        "gpa": "3.92",
        "ssn": "999-00-1111",  # Sensitive - will remain unrevealed
    }
    merkle_resp = client.post(
        "/api/v1/merkle/build-tree",
        json={"attributes": attributes},
        headers=admin_headers,
    )
    assert merkle_resp.status_code == 200
    tree_data = merkle_resp.json()
    merkle_root = tree_data["merkle_root"]
    salts = tree_data["salts"]

    # 5. Issue verifier challenge
    session_id = "verifier-session-xyz"
    challenge_resp = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert challenge_resp.status_code == 201
    ch_data = challenge_resp.json()
    challenge_id = ch_data["challenge_id"]
    challenge_nonce = ch_data["challenge_nonce"]

    # 6. Generate selective disclosure presentation (disclose 'degree' only, NOT 'ssn')
    issuer_id = "0x" + "1" * 64
    credential_id = "0x" + "2" * 64
    version = 1

    pres_gen_resp = client.post(
        "/api/v1/presentations/generate",
        json={
            "credential_id": credential_id,
            "version": version,
            "attributes": attributes,
            "salts": salts,
            "disclosed_keys": ["degree"],
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "issuer_id": issuer_id,
            "challenge_id": challenge_id,
            "challenge_nonce": challenge_nonce,
        },
        headers=admin_headers,
    )
    assert pres_gen_resp.status_code == 200
    presentation = pres_gen_resp.json()

    # Verify unrevealed attributes (ssn) are NOT in the presentation
    keys_in_pres = [c["key"] for c in presentation["disclosed_claims"]]
    assert "degree" in keys_in_pres
    assert "ssn" not in keys_in_pres

    # 7. Verifier submits presentation for verification
    verify_resp = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": presentation,
            "verifier_session_id": session_id,
        },
        headers=verifier_headers,
    )
    assert verify_resp.status_code == 200
    v_data = verify_resp.json()
    assert v_data["selective_disclosure_valid"] is True
    assert v_data["challenge_verified"] is True
    assert "degree" in v_data["disclosed_attributes"]
    assert v_data["disclosed_attributes"]["degree"] == "B.S. Software Engineering"

    # 8. Replay attempt with same challenge MUST be rejected (single-use replay prevention)
    replay_resp = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": presentation,
            "verifier_session_id": session_id,
        },
        headers=verifier_headers,
    )
    assert replay_resp.status_code == 409
    assert replay_resp.json()["error_code"] == "CHALLENGE_ALREADY_CONSUMED"


def test_tampered_claim_in_presentation_is_rejected(client, admin_headers, verifier_headers):
    """
    Guarantees that forging or altering a disclosed attribute value
    causes Merkle proof rejection.
    """
    attributes = {"degree": "B.S.", "gpa": "3.5"}
    merkle_resp = client.post(
        "/api/v1/merkle/build-tree",
        json={"attributes": attributes},
        headers=admin_headers,
    )
    tree_data = merkle_resp.json()

    # Generate presentation
    pres_gen = client.post(
        "/api/v1/presentations/generate",
        json={
            "credential_id": "0x" + "2" * 64,
            "version": 1,
            "attributes": attributes,
            "salts": tree_data["salts"],
            "disclosed_keys": ["gpa"],
            "document_digest": "0x" + "a" * 64,
            "metadata_digest": "0x" + "b" * 64,
            "issuer_id": "0x" + "c" * 64,
        },
        headers=admin_headers,
    ).json()

    # Tamper with disclosed GPA: claim 4.0 instead of 3.5
    pres_gen["disclosed_claims"][0]["value"] = "4.0"

    verify_resp = client.post(
        "/api/v1/presentations/verify",
        json={
            "presentation": pres_gen,
            "verifier_session_id": "any-session",
        },
        headers=verifier_headers,
    )
    assert verify_resp.status_code == 400
    assert verify_resp.json()["error_code"] == "INVALID_MERKLE_PROOF"
