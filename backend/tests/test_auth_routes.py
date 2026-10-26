import pytest
from fastapi.testclient import TestClient
from app.core.config import Settings
from app.main import app


def test_get_auth_config(client: TestClient):
    """GET /api/v1/auth/config must return current public authentication metadata."""
    res = client.get("/api/v1/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert "auth_mode" in data
    assert "environment" in data
    assert "dev_mode_available" in data
    assert "issuer_url" in data
    assert "audience" in data
    assert "allowed_algorithms" in data
    assert "RS256" in data["allowed_algorithms"]


def test_dev_token_generation_admin(client: TestClient):
    """POST /api/v1/auth/dev-token must issue a valid RS256 token for admin persona."""
    res = client.post("/api/v1/auth/dev-token", json={"persona": "admin"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert "admin" in data["roles"]
    assert data["sub"] == "admin-sec-ops"

    # Verify the token against /api/v1/auth/me
    token = data["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["subject"] == "admin-sec-ops"
    assert "admin" in me_data["roles"]
    assert me_data["is_admin"] is True


def test_dev_token_generation_issuer(client: TestClient):
    """POST /api/v1/auth/dev-token must issue a valid token for issuer persona with issuer_id."""
    issuer_id = "0x" + "aa" * 32
    res = client.post("/api/v1/auth/dev-token", json={"persona": "issuer", "issuer_id": issuer_id})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["roles"] == ["issuer"]
    assert data["issuer_id"].lower() == issuer_id.lower()

    # Verify against /api/v1/auth/me
    token = data["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["roles"] == ["issuer"]
    assert me_data["issuer_id"].lower() == issuer_id.lower()
    assert me_data["is_admin"] is False


def test_dev_token_generation_verifier(client: TestClient):
    """POST /api/v1/auth/dev-token must issue a valid token for verifier persona."""
    res = client.post("/api/v1/auth/dev-token", json={"persona": "verifier"})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["roles"] == ["verifier"]

    # Verify against /api/v1/auth/me
    token = data["access_token"]
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["roles"] == ["verifier"]
    assert me_data["verifier_id"] == "verifier-portal-auditor"


def test_dev_token_custom_persona(client: TestClient):
    """POST /api/v1/auth/dev-token must issue custom roles and claims."""
    res = client.post(
        "/api/v1/auth/dev-token",
        json={"persona": "custom", "roles": ["auditor", "verifier"], "sub": "custom-auditor-42"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["sub"] == "custom-auditor-42"
    assert "auditor" in data["roles"]
    assert "verifier" in data["roles"]


def test_unauthenticated_request_rejected(client: TestClient):
    """Protected /auth/me and /issuers must reject unauthenticated requests with HTTP 401."""
    res_me = client.get("/api/v1/auth/me")
    assert res_me.status_code == 401
    assert res_me.json()["error_code"] == "UNAUTHORIZED"

    res_iss = client.post("/api/v1/issuers", json={"issuer_id": "0x" + "11" * 32, "display_name": "Test"})
    assert res_iss.status_code == 401
    assert res_iss.json()["error_code"] == "UNAUTHORIZED"


def test_create_issuer_with_dev_admin_token(client: TestClient):
    """Creating an issuer with an admin dev-token must succeed with HTTP 201."""
    # Obtain admin dev token
    tok_res = client.post("/api/v1/auth/dev-token", json={"persona": "admin"})
    admin_token = tok_res.json()["access_token"]

    import uuid
    new_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    create_res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": new_id, "display_name": "Admin Registered University", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_res.status_code == 201
    assert create_res.json()["issuer_id"].lower() == new_id.lower()


def test_create_issuer_with_mismatched_issuer_token_rejected(client: TestClient):
    """An issuer token bound to issuer A cannot register issuer B (HTTP 403)."""
    issuer_a = "0x" + "11" * 32
    issuer_b = "0x" + "22" * 32

    tok_res = client.post("/api/v1/auth/dev-token", json={"persona": "issuer", "issuer_id": issuer_a})
    token = tok_res.json()["access_token"]

    create_res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": issuer_b, "display_name": "Mismatched Issuer", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 403
    assert create_res.json()["error_code"] == "INSUFFICIENT_PERMISSIONS"


def test_create_issuer_with_verifier_token_rejected(client: TestClient):
    """A verifier token cannot create an issuer (HTTP 403)."""
    tok_res = client.post("/api/v1/auth/dev-token", json={"persona": "verifier"})
    token = tok_res.json()["access_token"]

    create_res = client.post(
        "/api/v1/issuers",
        json={"issuer_id": "0x" + "33" * 32, "display_name": "Unauthorized Attempt", "status": "ACTIVE"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 403
    assert create_res.json()["error_code"] == "INSUFFICIENT_PERMISSIONS"


def test_dev_token_rejected_in_production(monkeypatch, client: TestClient):
    """In production mode, POST /api/v1/auth/dev-token must return HTTP 403."""
    from app.core import config
    monkeypatch.setattr(config.settings, "ENVIRONMENT", "production")

    res = client.post("/api/v1/auth/dev-token", json={"persona": "admin"})
    assert res.status_code == 403
    assert res.json()["error_code"] == "DEV_AUTH_FORBIDDEN"
