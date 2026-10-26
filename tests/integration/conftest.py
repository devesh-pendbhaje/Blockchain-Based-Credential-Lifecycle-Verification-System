import os
import sys
import pytest
import httpx

# Ensure backend directory is in Python path for importing cryptographic utilities
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

BACKEND_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
API_V1_URL = f"{BACKEND_BASE_URL}/api/v1"

@pytest.fixture(scope="session")
def backend_url() -> str:
    return BACKEND_BASE_URL

@pytest.fixture(scope="session")
def api_v1_url() -> str:
    return API_V1_URL

@pytest.fixture(scope="session")
def http_client():
    token = None
    try:
        with httpx.Client(base_url=BACKEND_BASE_URL, timeout=5.0) as temp_client:
            res = temp_client.post(f"{API_V1_URL}/auth/dev-token", json={"persona": "admin"})
            if res.status_code == 200:
                token = res.json().get("access_token")
    except Exception:
        pass

    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(base_url=BACKEND_BASE_URL, timeout=15.0, headers=headers) as client:
        yield client
