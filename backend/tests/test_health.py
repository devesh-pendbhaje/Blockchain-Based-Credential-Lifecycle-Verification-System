from unittest.mock import patch
from fastapi.testclient import TestClient


def test_liveness_endpoint(client: TestClient):
    """
    GET /health/live must always return 200 regardless of database connectivity.
    """
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "live"}

    # Also accessible via API v1 prefix
    v1_res = client.get("/api/v1/health/live")
    assert v1_res.status_code == 200
    assert v1_res.json() == {"status": "live"}


def test_readiness_healthy(client: TestClient):
    """
    GET /health/ready returns 200 when database connectivity succeeds.
    """
    with patch("app.api.routes.health.check_db_connectivity", return_value=True):
        response = client.get("/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"


def test_readiness_unhealthy(client: TestClient):
    """
    GET /health/ready returns 503 when database connectivity fails.
    """
    with patch("app.api.routes.health.check_db_connectivity", return_value=False):
        response = client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "disconnected"
