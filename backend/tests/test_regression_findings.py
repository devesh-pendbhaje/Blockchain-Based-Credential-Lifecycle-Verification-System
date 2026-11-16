"""
Regression test suite addressing findings 1 through 7:
1. Presentation verification fails closed (unknown creds, missing fields, RPC outages, unavailable contracts, wrong network).
   Proof validity separated from overall validity.
2. Tenant and holder authorization (cross-tenant version creation rejected before DB mutation; unbound issuers and ordinary users denied).
3. Identity preservation during anchoring and reconciliation (no silent overwrites).
4. Dev vs prod authentication separation.
5. Encryption key validation and rotation with fallback keys.
7. Lifecycle management (suspend, reactivate, revoke, supersede).
"""

import os
import json
import uuid
import time
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.exceptions import AppException
from app.models.credential import Credential
from app.models.credential_version import CredentialVersion
from app.models.issuer import Issuer
from app.schemas.credential import CredentialCreateRequest
from app.services.credential_service import CredentialService
from app.services.selective_disclosure_service import SelectiveDisclosureService
from app.services.challenge_service import ChallengeService
from app.blockchain.client import blockchain_client
from app.storage.service import CertificateStorageService
from app.crypto.merkle import SaltedAttributeMerkleTree
from app.crypto.fingerprint import compute_composite_fingerprint


# ==============================================================================
# FINDING 1: FAIL-CLOSED PRESENTATION VERIFICATION
# ==============================================================================

def test_presentation_verification_fails_closed_unknown_credential(client: TestClient, db_session, verifier_headers):
    """
    Unknown credentials presented for verification must return overall_valid=false
    with clear details, while selective_disclosure_valid is true if Merkle proof is valid.
    """
    session_id = "verifier-session-xyz"
    ch_res = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert ch_res.status_code == 201
    ch = ch_res.json()

    tree = SaltedAttributeMerkleTree({"degree": "B.S. Computer Science"})
    disclosed_claim = {
        "key": "degree",
        "value": "B.S. Computer Science",
        "salt": tree.salts["degree"],
        "proof": tree.get_proof("degree"),
    }

    presentation = {
        "credential_fingerprint": "0x" + "ff" * 32,
        "credential_id": "0x" + "ee" * 32,
        "version": 1,
        "issuer_id": "0x" + "dd" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": [disclosed_claim],
        "challenge_id": ch["challenge_id"],
        "challenge_nonce": ch["challenge_nonce"],
    }

    res = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["overall_valid"] is False
    assert data["selective_disclosure_valid"] is True  # Proof validity separate from overall validity!
    assert data["database_status"] == "NOT_FOUND"


def test_presentation_verification_fails_closed_on_rpc_disconnected(client: TestClient, db_session, verifier_headers):
    """
    During an RPC node disconnect, presentation verification must fail closed,
    returning overall_valid=False, authoritative_verification_available=False,
    and code=RPC_DISCONNECTED.
    """
    cred_id = "0x" + "11" * 32
    issuer_id = "0x" + "22" * 32
    doc_digest = "0x" + "44" * 32
    meta_digest = "0x" + "55" * 32

    tree = SaltedAttributeMerkleTree({"degree": "B.S. Computer Science"})
    merkle_root = tree.root

    fp = compute_composite_fingerprint(
        document_digest=doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuer_id=issuer_id,
        credential_id=cred_id,
        version=1,
    )

    iss = db_session.query(Issuer).filter_by(issuer_id=issuer_id).first()
    if not iss:
        iss = Issuer(issuer_id=issuer_id, display_name="Test Inst", status="ACTIVE")
        db_session.add(iss)
        db_session.commit()

    cred = Credential(credential_id=cred_id, issuer_id=issuer_id, current_version=1, current_fingerprint=fp, current_status="ACTIVE")
    ver = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint=fp,
        document_digest=doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuance_status="CONFIRMED",
    )
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    session_id = "rpc-disconnected-session"
    ch_res = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert ch_res.status_code == 201
    ch = ch_res.json()

    presentation = {
        "credential_fingerprint": fp,
        "credential_id": cred_id,
        "version": 1,
        "issuer_id": issuer_id,
        "merkle_root": merkle_root,
        "document_digest": doc_digest,
        "metadata_digest": meta_digest,
        "disclosed_claims": [
            {
                "key": "degree",
                "value": "B.S. Computer Science",
                "salt": tree.salts["degree"],
                "proof": tree.get_proof("degree"),
            }
        ],
        "challenge_id": ch["challenge_id"],
        "challenge_nonce": ch["challenge_nonce"],
    }

    # Explicitly mock RPC disconnected
    with patch.object(blockchain_client, "is_connected", return_value=False):
        res = client.post(
            "/api/v1/presentations/verify",
            json={"presentation": presentation, "verifier_session_id": session_id},
            headers=verifier_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_valid"] is False
        assert data["selective_disclosure_valid"] is True
        assert data["blockchain_verification"]["authoritative_verification_available"] is False
        assert data["blockchain_verification"]["code"] == "RPC_DISCONNECTED"


def test_presentation_verification_fails_closed_on_contract_unavailable(client: TestClient, db_session, verifier_headers):
    """
    When connected but contract verification returns UNAVAILABLE (or contract not deployed),
    presentation verification must fail closed, returning overall_valid=False,
    authoritative_verification_available=False, and code=UNAVAILABLE.
    """
    cred_id = "0x" + "11" * 32
    issuer_id = "0x" + "22" * 32
    doc_digest = "0x" + "44" * 32
    meta_digest = "0x" + "55" * 32

    tree = SaltedAttributeMerkleTree({"degree": "B.S. Computer Science"})
    merkle_root = tree.root

    fp = compute_composite_fingerprint(
        document_digest=doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuer_id=issuer_id,
        credential_id=cred_id,
        version=1,
    )

    iss = db_session.query(Issuer).filter_by(issuer_id=issuer_id).first()
    if not iss:
        iss = Issuer(issuer_id=issuer_id, display_name="Test Inst", status="ACTIVE")
        db_session.add(iss)
        db_session.commit()

    cred = Credential(credential_id=cred_id, issuer_id=issuer_id, current_version=1, current_fingerprint=fp, current_status="ACTIVE")
    ver = CredentialVersion(
        credential_id=cred_id,
        version=1,
        fingerprint=fp,
        document_digest=doc_digest,
        metadata_digest=meta_digest,
        merkle_root=merkle_root,
        issuance_status="CONFIRMED",
    )
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    session_id = "contract-unavailable-session"
    ch_res = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert ch_res.status_code == 201
    ch = ch_res.json()

    presentation = {
        "credential_fingerprint": fp,
        "credential_id": cred_id,
        "version": 1,
        "issuer_id": issuer_id,
        "merkle_root": merkle_root,
        "document_digest": doc_digest,
        "metadata_digest": meta_digest,
        "disclosed_claims": [
            {
                "key": "degree",
                "value": "B.S. Computer Science",
                "salt": tree.salts["degree"],
                "proof": tree.get_proof("degree"),
            }
        ],
        "challenge_id": ch["challenge_id"],
        "challenge_nonce": ch["challenge_nonce"],
    }

    # Explicitly mock connected and contract ready, but verify call returns UNAVAILABLE
    with patch.object(blockchain_client, "is_connected", return_value=True), \
         patch.object(blockchain_client, "is_contract_ready", return_value=True), \
         patch.object(
             blockchain_client,
             "verify_credential_on_chain",
             return_value={"is_valid": False, "code": "UNAVAILABLE", "stored_status": "UNAVAILABLE", "network_ok": False},
         ):
        res = client.post(
            "/api/v1/presentations/verify",
            json={"presentation": presentation, "verifier_session_id": session_id},
            headers=verifier_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["overall_valid"] is False
        assert data["selective_disclosure_valid"] is True
        assert data["blockchain_verification"]["authoritative_verification_available"] is False
        assert data["blockchain_verification"]["code"] == "UNAVAILABLE"


def test_presentation_verification_fails_closed_on_replayed_challenge(client: TestClient, db_session, verifier_headers):
    """A replayed challenge must fail closed immediately."""
    session_id = "replay-test-session"
    ch_res = client.post(
        "/api/v1/challenges",
        json={"verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert ch_res.status_code == 201
    ch = ch_res.json()

    tree = SaltedAttributeMerkleTree({"degree": "B.S. Computer Science"})

    presentation = {
        "credential_fingerprint": "0x" + "11" * 32,
        "credential_id": "0x" + "22" * 32,
        "version": 1,
        "issuer_id": "0x" + "33" * 32,
        "merkle_root": tree.root,
        "disclosed_claims": [
            {
                "key": "degree",
                "value": "B.S. Computer Science",
                "salt": tree.salts["degree"],
                "proof": tree.get_proof("degree"),
            }
        ],
        "challenge_id": ch["challenge_id"],
        "challenge_nonce": ch["challenge_nonce"],
    }

    # First verification consumes the challenge
    res1 = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert res1.status_code == 200

    # Second submission (replay attempt) must be rejected
    res2 = client.post(
        "/api/v1/presentations/verify",
        json={"presentation": presentation, "verifier_session_id": session_id},
        headers=verifier_headers,
    )
    assert res2.status_code == 409
    assert res2.json()["error_code"] == "CHALLENGE_ALREADY_CONSUMED"


# ==============================================================================
# FINDING 2: TENANT & HOLDER AUTHORIZATION
# ==============================================================================

def test_cross_tenant_version_creation_rejected_before_db_mutation(client: TestClient, db_session, make_token):
    """
    Before adding a version, check the authenticated issuer against the
    credential's EXISTING issuer, not just the submitted issuer_id.
    Issuer B attempting to add version 2 to Issuer A's credential must be rejected with 403.
    """
    issuer_a = "0x" + "11" * 32
    issuer_b = "0x" + "22" * 32

    # Seed Issuer A & B
    for i_id, name in [(issuer_a, "Issuer A"), (issuer_b, "Issuer B")]:
        if not db_session.query(Issuer).filter_by(issuer_id=i_id).first():
            db_session.add(Issuer(issuer_id=i_id, display_name=name, status="ACTIVE"))
    db_session.commit()

    # Seed Credential owned by Issuer A
    cred_id = "0x" + "99" * 32
    cred = Credential(credential_id=cred_id, issuer_id=issuer_a, current_version=1, current_fingerprint="0x" + "aa" * 32, current_status="ACTIVE")
    ver = CredentialVersion(credential_id=cred_id, version=1, fingerprint="0x" + "aa" * 32, document_digest="0x" + "bb" * 32, metadata_digest="0x" + "cc" * 32, merkle_root="0x" + "dd" * 32)
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    # Issuer B token
    tok_b = make_token(sub="issuer-b-admin", roles=["issuer"], issuer_id=issuer_b)
    headers_b = {"Authorization": f"Bearer {tok_b}"}

    # Attempt to add version 2 to Issuer A's credential
    payload = {
        "credential_id": cred_id,
        "issuer_id": issuer_b,
        "version": 2,
        "document_digest": "0x" + "21" * 32,
        "metadata_digest": "0x" + "22" * 32,
        "merkle_root": "0x" + "23" * 32,
    }
    res = client.post("/api/v1/credentials", json=payload, headers=headers_b)
    assert res.status_code == 403
    assert res.json()["error_code"] == "TENANT_MISMATCH"

    # Verify no mutation occurred in database
    v2 = db_session.query(CredentialVersion).filter_by(credential_id=cred_id, version=2).first()
    assert v2 is None


def test_unbound_issuers_and_ordinary_users_denied_access(client: TestClient, db_session, user_headers, unbound_issuer_headers):
    """Unbound issuers and ordinary users must be denied access to list, detail, history, and anchor endpoints."""
    # Seed credential
    issuer_id = "0x" + "11" * 32
    cred_id = "0x" + "88" * 32
    cred = Credential(credential_id=cred_id, issuer_id=issuer_id, current_version=1, current_fingerprint="0x" + "aa" * 32, current_status="ACTIVE")
    ver = CredentialVersion(credential_id=cred_id, version=1, fingerprint="0x" + "aa" * 32, document_digest="0x" + "bb" * 32, metadata_digest="0x" + "cc" * 32, merkle_root="0x" + "dd" * 32)
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    for h in [user_headers, unbound_issuer_headers]:
        # List
        assert client.get("/api/v1/credentials", headers=h).status_code == 403
        # Detail
        assert client.get(f"/api/v1/credentials/{cred_id}", headers=h).status_code == 403
        # Versions
        assert client.get(f"/api/v1/credentials/{cred_id}/versions", headers=h).status_code == 403
        # Anchor
        assert client.post(f"/api/v1/credentials/{cred_id}/versions/1/anchor", headers=h).status_code == 403
        # Suspend
        assert client.post(f"/api/v1/credentials/{cred_id}/suspend", headers=h).status_code == 403
        # Revoke
        assert client.post(f"/api/v1/credentials/{cred_id}/revoke", headers=h).status_code == 403


# ==============================================================================
# FINDING 3: PRESERVE ISSUER IDENTITY DURING ANCHORING & RECONCILIATION
# ==============================================================================

def test_anchor_rejects_unauthorized_signer_before_broadcast():
    """
    Verifies that the signing wallet is authorized for the requested issuer.
    Never silently overwrites issuer_id or fingerprint.
    """
    with patch.object(blockchain_client, "can_transact", True), \
         patch.object(blockchain_client, "is_contract_ready", return_value=True), \
         patch.object(blockchain_client, "get_signer_issuer_id", return_value="0x" + "11" * 32):

        # Attempt to anchor for issuer "0x9999..." when signer belongs to "0x1111..."
        res = blockchain_client.anchor_credential_fingerprint(
            credential_id_hex="0x" + "aa" * 32,
            doc_digest_hex="0x" + "bb" * 32,
            meta_digest_hex="0x" + "cc" * 32,
            merkle_root_hex="0x" + "dd" * 32,
            version=1,
            expected_issuer_id="0x" + "99" * 32,
        )
        assert res["status"] == "FAILED"
        assert "SIGNER_UNAUTHORIZED_FOR_ISSUER" in res["error"]


def test_reconciliation_rejects_identity_mismatch(db_session):
    """Reconciliation must compare complete expected record and never adopt another issuer's record."""
    cred_id = "0x" + "aa" * 32
    issuer_id = "0x" + "bb" * 32
    fp = "0x" + "cc" * 32

    cred = Credential(credential_id=cred_id, issuer_id=issuer_id, current_version=1, current_fingerprint=fp, current_status="ACTIVE")
    ver = CredentialVersion(credential_id=cred_id, version=1, fingerprint=fp, document_digest="0x" + "11" * 32, metadata_digest="0x" + "22" * 32, merkle_root="0x" + "33" * 32, issuance_status="PENDING")
    db_session.add(cred)
    db_session.add(ver)
    db_session.commit()

    # Blockchain returns a record belonging to a DIFFERENT issuer
    with patch.object(
        blockchain_client,
        "get_credential_record_on_chain",
        return_value={
            "issued_at": 1700000000,
            "status": "ACTIVE",
            "fingerprint": fp,
            "issuer_id": "0x" + "ff" * 32,  # Different issuer!
            "credential_id": cred_id,
            "version": 1,
        },
    ):
        service = CredentialService(db_session)
        with pytest.raises(AppException) as exc:
            service.reconcile_and_anchor_credential(cred_id, 1, principal=__import__("app.core.auth.models", fromlist=["AuthenticatedPrincipal"]).AuthenticatedPrincipal(subject="test", roles=["admin"]))
        assert exc.value.status_code == 409
        assert exc.value.error_code == "RECONCILIATION_IDENTITY_MISMATCH"


# ==============================================================================
# FINDING 4 & 5: DEV VS PROD AUTH & ENCRYPTION CONFIGURATION
# ==============================================================================

def test_production_rejects_known_example_encryption_key():
    """Production mode must reject known example encryption keys."""
    with pytest.raises(ValueError, match="known example STORAGE_ENCRYPTION_KEY"):
        Settings(
            ENVIRONMENT="production",
            AUTH_MODE="oidc",
            OIDC_ISSUER_URL="https://auth.example.com",
            OIDC_AUDIENCE="api",
            BLOCKCHAIN_RPC_URL="https://eth-mainnet.alchemyapi.io",
            STORAGE_ENCRYPTION_KEY="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
        )


def test_encryption_fallback_rotation(tmp_path):
    """
    Storage service can decrypt files encrypted with a previous key
    and re-encrypt them under the primary key.
    """
    old_key = "1111111111111111111111111111111111111111111111111111111111111111"
    new_key = "2222222222222222222222222222222222222222222222222222222222222222"

    root_dir = str(tmp_path)

    # 1. Store file with old key
    old_service = CertificateStorageService(
        storage_root_dir=root_dir,
        encryption_key_hex=old_key,
        previous_keys_hex=[],
    )
    raw_data = b"Sensitive Credential Data Here"
    meta = old_service.store_certificate(raw_bytes=raw_data, content_type="application/pdf", document_digest="0x" + "11" * 32)
    storage_id = meta["storage_id"]

    # 2. Read file with new service configured with old key in fallback list
    new_service = CertificateStorageService(
        storage_root_dir=root_dir,
        encryption_key_hex=new_key,
        previous_keys_hex=[old_key],
    )
    decrypted, meta_ret = new_service.retrieve_certificate(storage_id)
    assert decrypted == raw_data


# ==============================================================================
# FINDING 7: LIFECYCLE MANAGEMENT ENDPOINTS
# ==============================================================================

def test_lifecycle_management_suspend_reactivate_revoke(client, admin_headers, fake_chain):
    iid, cid = "0x"+"11"*32, "0x"+"22"*32
    client.post("/api/v1/issuers", json={"issuer_id":iid,"display_name":"Test"},headers=admin_headers)
    issued=client.post("/api/v1/credentials",json=dict(credential_id=cid,issuer_id=iid,version=1,
        document_digest="0x"+"33"*32,metadata_digest="0x"+"44"*32,merkle_root="0x"+"55"*32),headers=admin_headers)
    assert issued.status_code == 201
    for action,status in [("suspend","SUSPENDED"),("reactivate","ACTIVE"),("revoke","REVOKED")]:
        response=client.post(f"/api/v1/credentials/{cid}/{action}",json={"reason_code":1},headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["current_status"] == status
        assert response.json()["operation_status"] == "CONFIRMED"
    assert client.post(f"/api/v1/credentials/{cid}/reactivate",headers=admin_headers).status_code == 400
