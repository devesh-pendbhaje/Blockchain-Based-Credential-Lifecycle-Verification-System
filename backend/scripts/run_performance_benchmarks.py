import os
import sys
import time
import json
import secrets
import hmac
import hashlib
import statistics
import platform
from typing import List, Dict, Any

# Ensure backend root is on sys.path
backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.crypto.fingerprint import compute_composite_fingerprint
from app.crypto.merkle import SaltedAttributeMerkleTree, generate_salt, verify_merkle_proof
from app.crypto.metadata import canonicalize_and_hash_metadata
from app.storage.encryption import EnvelopeEncryption


def get_environment_info() -> Dict[str, Any]:
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "python_version": platform.python_version(),
        "machine": platform.machine(),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def calc_stats(latencies_ms: List[float]) -> Dict[str, float]:
    sorted_l = sorted(latencies_ms)
    n = len(sorted_l)
    return {
        "iterations": n,
        "mean_ms": round(statistics.mean(sorted_l), 4),
        "median_ms": round(statistics.median(sorted_l), 4),
        "min_ms": round(min(sorted_l), 4),
        "max_ms": round(max(sorted_l), 4),
        "p95_ms": round(sorted_l[int(n * 0.95)], 4) if n >= 20 else round(sorted_l[-1], 4),
        "p99_ms": round(sorted_l[int(n * 0.99)], 4) if n >= 100 else round(sorted_l[-1], 4),
        "ops_per_sec": round(n / (sum(sorted_l) / 1000.0), 2) if sum(sorted_l) > 0 else 0.0,
    }


def bench_composite_fingerprint(iterations: int = 5000) -> Dict[str, Any]:
    doc = "0x" + "aa" * 32
    meta = "0x" + "bb" * 32
    root = "0x" + "cc" * 32
    issuer = "0x" + "dd" * 32
    cred = "0x" + "ee" * 32
    ver = 1

    # Warmup
    for _ in range(100):
        compute_composite_fingerprint(doc, meta, root, issuer, cred, ver)

    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        compute_composite_fingerprint(doc, meta, root, issuer, cred, ver)
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1_000_000.0)

    stats = calc_stats(latencies)
    return {
        "benchmark": "Composite Fingerprint (6-input Keccak256)",
        "stats": stats,
    }


def bench_merkle_tree_scaling(leaf_counts: List[int] = [2, 4, 8, 16, 32, 64], iterations: int = 200) -> List[Dict[str, Any]]:
    results = []
    for count in leaf_counts:
        # Prepare attributes & salts
        attrs = {f"attr_{i:02d}": f"value_string_sample_{i}" for i in range(count)}
        salts = {k: generate_salt() for k in attrs}

        latencies_build = []
        latencies_proof = []
        latencies_verify = []

        # Warmup
        tree = SaltedAttributeMerkleTree(attrs, salts)
        proof = tree.get_proof("attr_00")
        verify_merkle_proof(proof, tree.root, tree.leaves["attr_00"])

        for _ in range(iterations):
            # Construction
            t0 = time.perf_counter_ns()
            tree = SaltedAttributeMerkleTree(attrs, salts)
            t1 = time.perf_counter_ns()
            latencies_build.append((t1 - t0) / 1_000_000.0)

            # Proof generation (first leaf)
            t2 = time.perf_counter_ns()
            proof = tree.get_proof("attr_00")
            t3 = time.perf_counter_ns()
            latencies_proof.append((t3 - t2) / 1_000_000.0)

            # Proof verification
            leaf_hash = tree.leaves["attr_00"]
            root = tree.root
            t4 = time.perf_counter_ns()
            valid = verify_merkle_proof(proof, root, leaf_hash)
            t5 = time.perf_counter_ns()
            latencies_verify.append((t5 - t4) / 1_000_000.0)
            assert valid

        results.append({
            "leaf_count": count,
            "build_stats": calc_stats(latencies_build),
            "proof_gen_stats": calc_stats(latencies_proof),
            "proof_verify_stats": calc_stats(latencies_verify),
        })

    return results


def bench_canonicalization(iterations: int = 1000) -> Dict[str, Any]:
    sample_metadata = {
        "student": {
            "name": "Alexandria Morgan",
            "id": 987654321,
            "honors": True,
            "dob": "2000-05-15",
        },
        "degree": {
            "title": "Master of Science in Computer Science",
            "major": "Artificial Intelligence & Distributed Systems",
            "gpa": 3.96,
            "credits_earned": 128,
        },
        "issuer": {
            "name": "Stanford University School of Engineering",
            "country": "US",
            "accreditation": "WASC",
        },
    }

    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        canonicalize_and_hash_metadata(sample_metadata)
        t1 = time.perf_counter_ns()
        latencies.append((t1 - t0) / 1_000_000.0)

    return {
        "benchmark": "RFC 8785 JSON Canonicalization (JCS)",
        "stats": calc_stats(latencies),
    }


def bench_aes_gcm_throughput(sizes_bytes: List[int] = [1024, 10_240, 102_400, 1_048_576, 5_242_880], iterations: int = 50) -> List[Dict[str, Any]]:
    key = b"0123456789abcdef0123456789abcdef"  # 32 bytes
    cipher = EnvelopeEncryption(key)
    results = []

    for size in sizes_bytes:
        data = os.urandom(size)
        enc_latencies = []
        dec_latencies = []

        # Warmup
        bundle = cipher.encrypt(data)
        cipher.decrypt(bundle)

        for _ in range(iterations):
            # Encryption
            t0 = time.perf_counter_ns()
            bundle = cipher.encrypt(data)
            t1 = time.perf_counter_ns()
            enc_latencies.append((t1 - t0) / 1_000_000.0)

            # Decryption
            t2 = time.perf_counter_ns()
            pt = cipher.decrypt(bundle)
            t3 = time.perf_counter_ns()
            dec_latencies.append((t3 - t2) / 1_000_000.0)
            assert pt == data

        avg_enc_sec = (sum(enc_latencies) / len(enc_latencies)) / 1000.0
        avg_dec_sec = (sum(dec_latencies) / len(dec_latencies)) / 1000.0
        size_mb = size / (1024 * 1024)

        results.append({
            "payload_size_bytes": size,
            "payload_label": f"{size // 1024} KB" if size < 1024*1024 else f"{size // (1024*1024)} MB",
            "encryption_stats": calc_stats(enc_latencies),
            "encryption_throughput_mb_s": round(size_mb / avg_enc_sec, 2) if avg_enc_sec > 0 else 0,
            "decryption_stats": calc_stats(dec_latencies),
            "decryption_throughput_mb_s": round(size_mb / avg_dec_sec, 2) if avg_dec_sec > 0 else 0,
        })

    return results


def bench_challenge_crypto(iterations: int = 2000) -> Dict[str, Any]:
    secret_key = b"institution-secret-hmac-key-256"
    latencies_gen = []
    latencies_hash = []
    latencies_verify = []

    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        nonce = "0x" + secrets.token_hex(32)
        t1 = time.perf_counter_ns()
        latencies_gen.append((t1 - t0) / 1_000_000.0)

        t2 = time.perf_counter_ns()
        digest = hmac.new(secret_key, bytes.fromhex(nonce[2:]), hashlib.sha256).hexdigest()
        t3 = time.perf_counter_ns()
        latencies_hash.append((t3 - t2) / 1_000_000.0)

        t4 = time.perf_counter_ns()
        expected = hmac.new(secret_key, bytes.fromhex(nonce[2:]), hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(digest, expected)
        t5 = time.perf_counter_ns()
        latencies_verify.append((t5 - t4) / 1_000_000.0)
        assert valid

    return {
        "nonce_generation_256bit": calc_stats(latencies_gen),
        "nonce_hmac_sha256_hash": calc_stats(latencies_hash),
        "nonce_constant_time_verification": calc_stats(latencies_verify),
    }


def bench_live_api_endpoints() -> Dict[str, Any]:
    import requests

    base_url = "http://127.0.0.1:8000/api/v1"
    results = {}

    try:
        # Check health
        health_resp = requests.get("http://127.0.0.1:8000/health/live", timeout=2)
        if health_resp.status_code != 200:
            return {"error": "Backend container offline"}
    except Exception as e:
        return {"error": f"Cannot connect to backend: {e}"}

    # 1. Dev token
    tok_resp = requests.post(f"{base_url}/auth/dev-token", json={"persona": "admin"})
    admin_token = tok_resp.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Public verification endpoint benchmark
    fp = "0xa5925f830b0488f75940061910f73c7027a7049e537b229e37d45e7ef438ef77"
    verify_latencies = []
    for _ in range(25):
        t0 = time.perf_counter_ns()
        r = requests.get(f"{base_url}/credentials/fingerprint/{fp}/verify")
        t1 = time.perf_counter_ns()
        assert r.status_code == 200
        verify_latencies.append((t1 - t0) / 1_000_000.0)

    results["public_verification_endpoint"] = calc_stats(verify_latencies)

    # 3. Challenge issuance endpoint benchmark
    ch_latencies = []
    for i in range(25):
        sess = f"bench-session-{i}-{time.time()}"
        t0 = time.perf_counter_ns()
        r = requests.post(f"{base_url}/challenges", json={"verifier_session_id": sess}, headers=admin_headers)
        t1 = time.perf_counter_ns()
        assert r.status_code == 201
        ch_latencies.append((t1 - t0) / 1_000_000.0)

    results["challenge_issuance_endpoint"] = calc_stats(ch_latencies)

    # 4. Merkle build tree endpoint benchmark
    merkle_latencies = []
    attrs = {"claim_a": "val_1", "claim_b": "val_2", "claim_c": "val_3", "claim_d": "val_4"}
    for _ in range(25):
        t0 = time.perf_counter_ns()
        r = requests.post(f"{base_url}/merkle/build-tree", json={"attributes": attrs}, headers=admin_headers)
        t1 = time.perf_counter_ns()
        assert r.status_code == 200
        merkle_latencies.append((t1 - t0) / 1_000_000.0)

    results["merkle_build_tree_endpoint"] = calc_stats(merkle_latencies)

    # 5. List credentials endpoint benchmark
    list_latencies = []
    for _ in range(25):
        t0 = time.perf_counter_ns()
        r = requests.get(f"{base_url}/credentials?limit=20", headers=admin_headers)
        t1 = time.perf_counter_ns()
        assert r.status_code == 200
        list_latencies.append((t1 - t0) / 1_000_000.0)

    results["list_credentials_endpoint"] = calc_stats(list_latencies)

    return results


def run_all_benchmarks() -> Dict[str, Any]:
    print("=" * 70)
    print("RUNNING REPRODUCIBLE SYSTEM PERFORMANCE BENCHMARKS")
    print("=" * 70)

    env = get_environment_info()
    print(f"Environment: {env['platform']} | CPU: {env['processor']} ({env['cpu_count']} cores)")
    print(f"Python: {env['python_version']} | Timestamp: {env['timestamp_utc']}")
    print("-" * 70)

    print("[1/5] Benchmarking 6-Input Composite Fingerprint (5,000 iterations)...")
    fp_bench = bench_composite_fingerprint(5000)
    print(f"      Mean: {fp_bench['stats']['mean_ms']} ms | Throughput: {fp_bench['stats']['ops_per_sec']} ops/sec")

    print("[2/5] Benchmarking Salted Attribute Merkle Tree Scaling (N=2 to 64 leaves)...")
    merkle_bench = bench_merkle_tree_scaling([2, 4, 8, 16, 32, 64], 200)
    for m in merkle_bench:
        print(f"      Leaves={m['leaf_count']:2d} -> Build: {m['build_stats']['mean_ms']} ms | Proof: {m['proof_gen_stats']['mean_ms']} ms | Verify: {m['proof_verify_stats']['mean_ms']} ms")

    print("[3/5] Benchmarking RFC 8785 JSON Canonicalization (1,000 iterations)...")
    canon_bench = bench_canonicalization(1000)
    print(f"      Mean: {canon_bench['stats']['mean_ms']} ms | Throughput: {canon_bench['stats']['ops_per_sec']} ops/sec")

    print("[4/5] Benchmarking AES-256-GCM Envelope Encryption & Decryption Throughput...")
    aes_bench = bench_aes_gcm_throughput([1024, 10_240, 102_400, 1_048_576, 5_242_880], 50)
    for a in aes_bench:
        print(f"      Payload: {a['payload_label']:>5s} -> Encrypt: {a['encryption_throughput_mb_s']:7.2f} MB/s | Decrypt: {a['decryption_throughput_mb_s']:7.2f} MB/s")

    print("[5/5] Benchmarking Live HTTP Endpoints on Container...")
    api_bench = bench_live_api_endpoints()
    for ep, st in api_bench.items():
        if isinstance(st, dict) and "mean_ms" in st:
            print(f"      {ep:35s}: Mean: {st['mean_ms']:7.2f} ms | P95: {st['p95_ms']:7.2f} ms")

    challenge_crypto_bench = bench_challenge_crypto(2000)

    return {
        "environment": env,
        "composite_fingerprint": fp_bench,
        "merkle_scaling": merkle_bench,
        "canonicalization": canon_bench,
        "aes_gcm_throughput": aes_bench,
        "challenge_crypto": challenge_crypto_bench,
        "live_api_endpoints": api_bench,
    }


if __name__ == "__main__":
    report_data = run_all_benchmarks()
    out_path = os.path.join(backend_root, "..", "docs", "experiments", "benchmark_raw_results.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print("-" * 70)
    print(f"Benchmark results saved to: {out_path}")
    print("=" * 70)
