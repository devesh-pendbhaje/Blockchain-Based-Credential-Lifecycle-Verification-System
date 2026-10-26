import uuid
import concurrent.futures
import time
import pytest
import httpx
from app.crypto.merkle import SaltedAttributeMerkleTree

def test_workflow_d_selective_disclosure_and_challenge_response(http_client: httpx.Client, api_v1_url: str):
    """
    Workflow D: Selective Disclosure & Challenge-Response
    1. Create credential with 4 attributes.
    2. Request verifier challenge nonce bound to session.
    3. Generate presentation disclosing only selected subset.
    4. Verify unselected attributes absent.
    5. Verify Merkle proof.
    6. Verify presentation successfully.
    7. Attempt replay -> reject 409 CHALLENGE_ALREADY_CONSUMED.
    8. Attempt cross-session mismatch -> reject 403 VERIFIER_SESSION_MISMATCH.
    9. Attempt cross-credential mismatch -> reject 403 CHALLENGE_SCOPE_MISMATCH.
    10. Enforce atomic single-use consumption under concurrent requests.
    """
    # 1. Setup Issuer & Credential
    raw_issuer = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_issuer
    http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": issuer_id, "display_name": "Selective Disclosure University", "status": "ACTIVE"},
    )

    attributes = {
        "degree": "Master of Science in Cybersecurity",
        "student_name": "Alice Developer",
        "gpa": "3.95",
        "honors": "Distinction",
    }
    tree = SaltedAttributeMerkleTree(attributes)
    raw_cred = uuid.uuid4().hex + uuid.uuid4().hex
    credential_id = "0x" + raw_cred
    doc_digest = "0x" + "a" * 64
    meta_digest = "0x" + "b" * 64

    issue_resp = http_client.post(
        f"{api_v1_url}/credentials",
        json={
            "credential_id": credential_id,
            "issuer_id": issuer_id,
            "version": 1,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": tree.root,
            "expires_at": 0,
        },
    )
    assert issue_resp.status_code == 201
    cred_fingerprint = issue_resp.json()["current_fingerprint"]

    # 2. Request Verifier Challenge Nonce
    verifier_session_id = f"session-{uuid.uuid4().hex}"
    chal_resp = http_client.post(
        f"{api_v1_url}/challenges",
        json={
            "verifier_session_id": verifier_session_id,
            "credential_fingerprint": cred_fingerprint,
            "expiry_seconds": 300,
        },
    )
    assert chal_resp.status_code == 201
    chal_data = chal_resp.json()
    challenge_id = chal_data["challenge_id"]
    challenge_nonce = chal_data["challenge_nonce"]
    assert challenge_nonce.startswith("0x")
    assert len(challenge_nonce) == 66

    # 3. Generate Selective Disclosure Presentation (reveal only degree and honors)
    disclosed_keys = ["degree", "honors"]
    gen_resp = http_client.post(
        f"{api_v1_url}/presentations/generate",
        json={
            "credential_id": credential_id,
            "version": 1,
            "attributes": attributes,
            "salts": tree.salts,
            "disclosed_keys": disclosed_keys,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "issuer_id": issuer_id,
            "challenge_id": challenge_id,
            "challenge_nonce": challenge_nonce,
        },
    )
    assert gen_resp.status_code == 200
    presentation = gen_resp.json()

    # 4 & 5. Verify unselected attributes are absent from presentation
    revealed_keys = [c["key"] for c in presentation["disclosed_claims"]]
    assert set(revealed_keys) == set(disclosed_keys)
    assert "student_name" not in revealed_keys
    assert "gpa" not in revealed_keys

    # 6. Verify Presentation
    verify_resp = http_client.post(
        f"{api_v1_url}/presentations/verify",
        json={
            "presentation": presentation,
            "verifier_session_id": verifier_session_id,
        },
    )
    assert verify_resp.status_code == 200
    v_out = verify_resp.json()
    assert v_out["selective_disclosure_valid"] is True
    assert v_out["challenge_verified"] is True
    assert v_out["fingerprint_verified"] is True
    assert "degree" in v_out["disclosed_attributes"]
    assert "honors" in v_out["disclosed_attributes"]

    # 7. Attempt Replay Attack with consumed challenge
    replay_resp = http_client.post(
        f"{api_v1_url}/presentations/verify",
        json={
            "presentation": presentation,
            "verifier_session_id": verifier_session_id,
        },
    )
    assert replay_resp.status_code == 409
    assert replay_resp.json()["error_code"] == "CHALLENGE_ALREADY_CONSUMED"

    # 8. Attempt Session Mismatch: create challenge for session A, verify with session B
    session_a = f"session-a-{uuid.uuid4().hex}"
    session_b = f"session-b-{uuid.uuid4().hex}"
    chal2_resp = http_client.post(
        f"{api_v1_url}/challenges",
        json={"verifier_session_id": session_a, "credential_fingerprint": cred_fingerprint},
    )
    chal2 = chal2_resp.json()
    pres2 = dict(presentation)
    pres2["challenge_id"] = chal2["challenge_id"]
    pres2["challenge_nonce"] = chal2["challenge_nonce"]

    mismatch_resp = http_client.post(
        f"{api_v1_url}/presentations/verify",
        json={"presentation": pres2, "verifier_session_id": session_b},
    )
    assert mismatch_resp.status_code == 403
    assert mismatch_resp.json()["error_code"] == "VERIFIER_SESSION_MISMATCH"

    # 9. Attempt Scope Mismatch: challenge scoped to fingerprint A, presentation has fingerprint B
    chal3_resp = http_client.post(
        f"{api_v1_url}/challenges",
        json={"verifier_session_id": session_a, "credential_fingerprint": "0x" + "9" * 64},
    )
    chal3 = chal3_resp.json()
    pres3 = dict(presentation)
    pres3["challenge_id"] = chal3["challenge_id"]
    pres3["challenge_nonce"] = chal3["challenge_nonce"]

    scope_resp = http_client.post(
        f"{api_v1_url}/presentations/verify",
        json={"presentation": pres3, "verifier_session_id": session_a},
    )
    assert scope_resp.status_code == 403
    assert scope_resp.json()["error_code"] == "CHALLENGE_SCOPE_MISMATCH"


def test_concurrent_challenge_consumption(http_client: httpx.Client, api_v1_url: str):
    """
    Test atomic single-use behavior under concurrent requests.
    Issue 1 challenge, launch 10 concurrent requests to consume it.
    Exactly 1 request must succeed (HTTP 200), and 9 requests must fail with HTTP 409.
    """
    # Create issuer and credential
    raw_issuer = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_issuer
    http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": issuer_id, "display_name": "Concurrent Test Authority", "status": "ACTIVE"},
    )

    attributes = {"test_claim": "concurrent_value"}
    tree = SaltedAttributeMerkleTree(attributes)
    cred_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    doc_digest = "0x" + "c" * 64
    meta_digest = "0x" + "d" * 64

    issue_resp = http_client.post(
        f"{api_v1_url}/credentials",
        json={
            "credential_id": cred_id,
            "issuer_id": issuer_id,
            "version": 1,
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "merkle_root": tree.root,
            "expires_at": 0,
        },
    )
    assert issue_resp.status_code == 201
    cred_fp = issue_resp.json()["current_fingerprint"]

    # Issue 1 challenge
    session_id = f"concurrent-session-{uuid.uuid4().hex}"
    chal_resp = http_client.post(
        f"{api_v1_url}/challenges",
        json={"verifier_session_id": session_id, "credential_fingerprint": cred_fp},
    )
    chal = chal_resp.json()

    gen_resp = http_client.post(
        f"{api_v1_url}/presentations/generate",
        json={
            "credential_id": cred_id,
            "version": 1,
            "attributes": attributes,
            "salts": tree.salts,
            "disclosed_keys": ["test_claim"],
            "document_digest": doc_digest,
            "metadata_digest": meta_digest,
            "issuer_id": issuer_id,
            "challenge_id": chal["challenge_id"],
            "challenge_nonce": chal["challenge_nonce"],
        },
    )
    presentation = gen_resp.json()

    def submit_verify():
        with httpx.Client(timeout=15.0) as client:
            return client.post(
                f"{api_v1_url}/presentations/verify",
                json={"presentation": presentation, "verifier_session_id": session_id},
            )

    # Launch 10 concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(submit_verify) for _ in range(10)]
        results = [f.result() for f in futures]

    status_codes = [r.status_code for r in results]
    success_count = status_codes.count(200)
    conflict_count = status_codes.count(409)

    assert success_count == 1, f"Expected exactly 1 successful consumption, got {success_count}. Statuses: {status_codes}"
    assert conflict_count == 9, f"Expected exactly 9 conflict rejections, got {conflict_count}. Statuses: {status_codes}"
