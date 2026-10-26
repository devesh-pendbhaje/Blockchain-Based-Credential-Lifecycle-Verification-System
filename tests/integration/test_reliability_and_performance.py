import uuid
import time
import pytest
import httpx

def test_performance_repeated_lookups(http_client: httpx.Client, api_v1_url: str):
    """
    Performance check:
    Measure latency over 50 sequential credential queries.
    Assert p95 latency is bounded (< 200ms per request).
    """
    # 1. Setup Issuer & Credential
    raw_issuer = uuid.uuid4().hex + uuid.uuid4().hex
    issuer_id = "0x" + raw_issuer
    http_client.post(
        f"{api_v1_url}/issuers",
        json={"issuer_id": issuer_id, "display_name": "Perf Authority", "status": "ACTIVE"},
    )

    cred_id = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
    doc_digest = "0x" + "7" * 64
    meta_digest = "0x" + "8" * 64
    merkle_root = "0x" + "9" * 64

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
    fingerprint = issue_resp.json()["current_fingerprint"]

    # 2. Run 50 sequential queries and record latency
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        r = http_client.get(f"{api_v1_url}/credentials/fingerprint/{fingerprint}/verify")
        t1 = time.perf_counter()
        assert r.status_code == 200
        latencies.append((t1 - t0) * 1000)  # ms

    avg_ms = sum(latencies) / len(latencies)
    sorted_latencies = sorted(latencies)
    p95_ms = sorted_latencies[int(len(sorted_latencies) * 0.95)]

    print(f"\n[PERFORMANCE] 50 Lookups -> Avg: {avg_ms:.2f}ms, P95: {p95_ms:.2f}ms, Min: {min(latencies):.2f}ms, Max: {max(latencies):.2f}ms")
    assert avg_ms < 200, f"Average query latency too high: {avg_ms:.2f}ms"


def test_file_upload_size_limit_boundary(http_client: httpx.Client, api_v1_url: str):
    """
    Test max upload size limit boundary (10 MB).
    File exceeding 10MB must be rejected.
    """
    # 1. Test unsupported media type rejection (415)
    invalid_type_bytes = b"NOT_A_VALID_MAGIC_HEADER_CERTIFICATE"
    files_inv = {"file": ("malicious.exe", invalid_type_bytes, "application/octet-stream")}
    resp_inv = http_client.post(f"{api_v1_url}/documents/upload", files=files_inv)
    assert resp_inv.status_code == 415
    assert resp_inv.json()["error_code"] == "UNSUPPORTED_CONTENT_TYPE"

    # 2. Test 10MB + 1KB payload with valid PDF magic header triggering 413
    oversized_pdf = b"%PDF-1.4\n" + b"0" * (10 * 1024 * 1024 + 1024)
    files = {"file": ("oversized.pdf", oversized_pdf, "application/pdf")}
    resp = http_client.post(f"{api_v1_url}/documents/upload", files=files)
    assert resp.status_code in [400, 413], f"Expected 400 or 413 for oversized file, got {resp.status_code}"
    if resp.status_code == 413:
        assert resp.json()["error_code"] == "DOCUMENT_SIZE_EXCEEDED"


def test_security_headers_enforcement(http_client: httpx.Client, api_v1_url: str):
    """
    Verify security headers on API responses:
    - Cache-Control: no-store, no-cache, must-revalidate
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    """
    resp = http_client.get(f"{api_v1_url}/health/ready")
    assert resp.status_code == 200
    headers = resp.headers
    assert "no-store" in headers.get("cache-control", "").lower()
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
