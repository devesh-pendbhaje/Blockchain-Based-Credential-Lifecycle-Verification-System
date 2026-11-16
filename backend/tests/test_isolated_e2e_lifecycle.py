"""API integration using an explicit stateful chain double.
Real deployed-contract end-to-end coverage lives in scripts/verify_local_e2e.py.
"""
from app.models.issuer import Issuer
from app.crypto.merkle import SaltedAttributeMerkleTree


def test_isolated_e2e_credential_lifecycle(client, db_session, issuer_headers, verifier_headers, holder_headers, fake_chain):
    issuer_id = "0x" + "11" * 32
    db_session.add(Issuer(issuer_id=issuer_id, display_name="Test University", status="ACTIVE"))
    db_session.commit()
    attributes = {"degree": "Computer Science", "privateNote": "Never disclose"}
    tree = SaltedAttributeMerkleTree(attributes=attributes)
    payload = dict(credential_id="0x" + "ab" * 32, issuer_id=issuer_id, version=1,
                   document_digest="0x" + "12" * 32, metadata_digest="0x" + "34" * 32,
                   merkle_root=tree.root)
    issued = client.post("/api/v1/credentials", json=payload, headers=issuer_headers)
    assert issued.status_code == 201
    assert issued.json()["issuance_status"] == "CONFIRMED"
    assert issued.json()["current_status"] == "ACTIVE"
    session = "test-verifier-session"

    def verify(expected):
        challenge = client.post("/api/v1/challenges", json={"verifier_session_id": session}, headers=verifier_headers)
        assert challenge.status_code == 201
        request = {k:v for k,v in payload.items() if k != "merkle_root"}
        request.update(attributes=attributes, salts=tree.salts, disclosed_keys=["degree"],
                       challenge_id=challenge.json()["challenge_id"], challenge_nonce=challenge.json()["challenge_nonce"])
        generated = client.post("/api/v1/presentations/generate", json=request, headers=holder_headers)
        assert generated.status_code == 200
        assert [c["key"] for c in generated.json()["disclosed_claims"]] == ["degree"]
        assert "Never disclose" not in generated.text
        request = dict(presentation=generated.json(), verifier_session_id=session, require_current_version=True)
        checked = client.post("/api/v1/presentations/verify", json=request, headers=verifier_headers)
        assert checked.status_code == 200
        assert checked.json()["overall_valid"] is expected
        replay = client.post("/api/v1/presentations/verify", json=request, headers=verifier_headers)
        assert replay.status_code == 409

    verify(True)
    for action, state, valid in [("suspend", "SUSPENDED", False), ("reactivate", "ACTIVE", True), ("revoke", "REVOKED", False)]:
        response = client.post(f"/api/v1/credentials/{payload['credential_id']}/{action}", json={"reason_code":1}, headers=issuer_headers)
        assert response.status_code == 200
        assert response.json()["current_status"] == state
        verify(valid)
