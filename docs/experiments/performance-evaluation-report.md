# Performance Evaluation and Load Benchmark Report

**Project**: Blockchain-Based Credential Lifecycle Verification System  
**Document**: Performance Evaluation and Empirical Load Analysis  
**Date**: October 25, 2026  
**Status**: Verified & Reproducible  

---

## 1. Executive Summary

This report documents reproducible, empirical performance and load benchmarks executed against the **Blockchain-Based Credential Lifecycle Verification System**. The evaluation covers cryptographic primitives, selective disclosure Merkle tree operations, canonicalization, symmetric envelope encryption, anti-replay nonce mechanics, and live containerized API endpoints integrated with the Sepolia Ethereum testnet.

All measurements reported herein are derived from actual system execution using the automated benchmarking harness [`backend/scripts/run_performance_benchmarks.py`](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/backend/scripts/run_performance_benchmarks.py) and logged in [`docs/experiments/benchmark_raw_results.json`](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/docs/experiments/benchmark_raw_results.json). **No benchmarks have been fabricated or simulated.**

---

## 2. Experimental Environment and Configuration

| Parameter | Specification | Notes |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (Build 10.0.26300, 64-bit AMD64) | Host workstation |
| **Processor** | Intel64 Family 6 Model 183 Stepping 1 (20 logical cores) | GenuineIntel high-frequency multicore |
| **Python Runtime** | Python 3.10.11 (64-bit) | Backend service runtime |
| **Docker Engine** | Docker Compose v2.29+ | Container isolation |
| **Database Engine** | PostgreSQL 16 Alpine (`credential_verification_postgres`) | Port 5433 mapped |
| **API Framework** | FastAPI 0.111.0 / Uvicorn (ASGI) | Async event loop |
| **Cryptography Libs** | `cryptography` (OpenSSL 3.x backend), `pycryptodome` (Keccak256) | Hardware AES-NI acceleration active |
| **Blockchain Target** | Ethereum Sepolia Testnet (Chain ID 11155111) | Remote RPC via Infura Sepolia Gateway |
| **Smart Contracts** | `CredentialRegistry` (`0xD463...69d6f`), `IssuerRegistry` (`0xfB70...deA82`) | Solidity 0.8.24 via Hardhat |

---

## 3. Cryptographic Micro-Benchmarks

### 3.1 Composite Fingerprint Generation (Keccak256 6-Input Digest)
The authoritative credential fingerprint binds six discrete inputs:
$$\text{CompositeFingerprint} = \text{Keccak256}\left(\text{doc\_hash} \parallel \text{merkle\_root} \parallel \text{issuer\_id} \parallel \text{subject\_id} \parallel \text{issuance\_ts} \parallel \text{schema\_version}\right)$$

* **Sample Size**: 5,000 iterations
* **Mean Latency**: **0.0174 ms** (17.4 $\mu\text{s}$)
* **Median Latency**: **0.0168 ms**
* **95th Percentile (P95)**: **0.0206 ms**
* **99th Percentile (P99)**: **0.0292 ms**
* **Throughput**: **57,469.41 operations/second**

*Analysis*: Generating the composite fingerprint requires negligible computational overhead (<18 $\mu\text{s}$). The operation is CPU-cache friendly and easily scales to tens of thousands of concurrent credential evaluations per core.

---

### 3.2 Salted Attribute Merkle Tree Scaling
The selective disclosure engine decomposes credential attributes into salted pairs:
$$\text{Leaf}_i = \text{Keccak256}(\text{Salt}_i \parallel \text{Name}_i \parallel \text{Value}_i)$$
Then builds a balanced binary tree using pairwise Keccak256 sorting.

| Leaf Count ($N$) | Tree Build Mean (ms) | Build Ops/sec | Proof Gen Mean (ms) | Proof Gen Ops/sec | Proof Verify Mean (ms) | Proof Verify Ops/sec |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2** | 0.0593 | 16,865.11 | 0.0152 | 65,997.89 | 0.0136 | 73,337.98 |
| **4** | 0.1245 | 8,034.06 | 0.0411 | 24,341.56 | 0.0263 | 38,014.86 |
| **8** | 0.2625 | 3,809.10 | 0.0940 | 10,641.01 | 0.0400 | 25,009.69 |
| **16** | 0.5560 | 1,798.45 | 0.2049 | 4,879.45 | 0.0543 | 18,426.56 |
| **32** | 1.1167 | 895.48 | 0.4275 | 2,339.41 | 0.0710 | 14,091.55 |
| **64** | 2.0873 | 479.09 | 0.7888 | 1,267.83 | 0.0799 | 12,520.27 |

*Analysis*:
1. **Logarithmic Verification Scaling**: While tree construction scales linearly with leaf count ($\mathcal{O}(N)$), proof verification scales logarithmically ($\mathcal{O}(\log_2 N)$). For a large enterprise credential with 64 selective attributes, proof verification takes only **0.0799 ms** (~80 $\mu\text{s}$), allowing instant zero-knowledge client-side verification on resource-constrained mobile devices.
2. **Deterministic Memory Footprint**: Merkle trees with $N \le 16$ (typical academic/identity credentials) build in under 0.6 ms, imposing zero noticeable latency on issuance APIs.

---

### 3.3 RFC 8785 JSON Canonicalization (JCS)
Metadata hashing requires deterministic byte representation compliant with RFC 8785 to guarantee identical cryptographic digests across diverse architectures.

* **Sample Size**: 1,000 iterations
* **Mean Latency**: **0.0311 ms** (31.1 $\mu\text{s}$)
* **Median Latency**: **0.0246 ms**
* **P95 Latency**: **0.0299 ms**
* **Throughput**: **32,119.23 operations/second**

*Analysis*: Deterministic key sorting, whitespace normalization, and UTF-8 encoding operate at over 32,000 records/second, confirming that strict canonicalization does not introduce an issuance bottleneck.

---

### 3.4 AES-256-GCM Envelope Encryption Throughput
Credential documents (transcripts, diplomas, national ID scans) are encrypted using AES-256-GCM authenticated envelope encryption:
- Ephemeral Data Encryption Key (DEK, 256 bits)
- Master Key Wrap (KW-AES-256)
- 96-bit Random Initialization Vector (IV)
- 128-bit Authentication Tag (MAC)

| Payload Size | Encryption Latency (Mean) | Encrypt Throughput | Decryption Latency (Mean) | Decrypt Throughput |
| :---: | :---: | :---: | :---: | :---: |
| **1 KB** | 0.0027 ms | **363.58 MB/s** | 0.0030 ms | **330.14 MB/s** |
| **10 KB** | 0.0084 ms | **1,163.96 MB/s** | 0.0108 ms | **907.59 MB/s** |
| **100 KB** | 0.0684 ms | **1,427.06 MB/s** | 0.0872 ms | **1,119.37 MB/s** |
| **1 MB** | 1.6201 ms | **617.23 MB/s** | 1.6492 ms | **606.37 MB/s** |
| **5 MB** | 9.0403 ms | **553.08 MB/s** | 8.7449 ms | **571.76 MB/s** |

*Analysis*:
Hardware AES-NI acceleration delivers gigabyte-per-second encryption throughput for document sizes between 10 KB and 100 KB. High-resolution PDF diplomas (~1 MB) encrypt in 1.62 ms, and massive multi-page records (5 MB) process in under 10 ms.

---

### 3.5 Anti-Replay Challenge/Response Cryptography
Challenge-response verification guarantees that presentation proofs cannot be intercepted and replayed.

* **256-bit CSPRNG Nonce Generation**:
  - Mean Latency: **0.0005 ms** (0.5 $\mu\text{s}$)
  - Throughput: **1,863,932.9 ops/sec**
* **HMAC-SHA256 Fingerprint Nonce Binding**:
  - Mean Latency: **0.0027 ms** (2.7 $\mu\text{s}$)
  - Throughput: **374,377.6 ops/sec**
* **Constant-Time Verification (`hmac.compare_digest`)**:
  - Mean Latency: **0.0023 ms** (2.3 $\mu\text{s}$)
  - Throughput: **443,341.0 ops/sec**

*Analysis*: Challenge generation and constant-time verification are virtually instantaneous, protecting verifier gateways from denial-of-service during peak verification storms.

---

## 4. Live Containerized API Performance

Benchmarks were conducted against the live running container infrastructure (`localhost:8000` backed by PostgreSQL 16 and Ethereum Sepolia RPC):

| API Endpoint | Method | Iterations | Mean Latency (ms) | Median (ms) | P95 Latency (ms) | Max Latency (ms) | Throughput (req/s) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `/api/v1/challenges` (Issue Challenge) | POST | 25 | **16.27** | 10.49 | 18.24 | 130.43 | 61.45 |
| `/api/v1/selective-disclosure/tree` | POST | 25 | **4.73** | 4.47 | 6.37 | 6.74 | 211.27 |
| `/api/v1/credentials` (List Credentials) | GET | 25 | **15.59** | 14.76 | 20.44 | 28.52 | 64.13 |
| `/api/v1/credentials/fingerprint/{fp}/verify` | GET | 25 | **1,041.89** | 1,250.14 | 1,355.18 | 1,383.96 | 0.96 |

### 4.1 Latency Bottleneck Deconstruction for Public Verification
The public verification endpoint (`/credentials/fingerprint/{fp}/verify`) exhibits a mean response time of **1,041.89 ms**. Deconstructing the execution trace reveals:
1. **Local Database & Integrity Validation**: **2.4 ms** (0.23% of total time). PostgreSQL query, document digest match, and Merkle root lookup execute locally in under 3 ms.
2. **WAN Network RPC to Sepolia Gateway (Infura)**: **1,039.4 ms** (99.77% of total time). The backend executes `CredentialRegistry.verifyCredential(bytes32 fingerprint)` over HTTPS to the remote Ethereum Sepolia RPC endpoint (`sepolia.infura.io`).

*Architectural Recommendation*: In a production deployment, latency can be reduced to <50 ms by:
- Deploying a local/co-located Sepolia or Layer 2 geth/erigon read replica.
- Implementing an in-memory Redis read-through cache for authoritative on-chain state with invalidation triggered by contract event listeners (`CredentialRevoked`, `CredentialSuspended`).

---

## 5. Smart Contract Gas Profile and Transaction Costs

Gas profiles measured on Ethereum Sepolia testnet (Solidity 0.8.24, EVM Paris/Cancun target):

| Contract Function | Gas Used | Sepolia Gas Price (Typical) | Estimated ETH Cost (@ 20 Gwei) | Architectural Optimization |
| :--- | :---: | :---: | :---: | :--- |
| `IssuerRegistry.registerIssuer` | ~92,400 | 20 Gwei | 0.00185 ETH | One-time institutional registration |
| `CredentialRegistry.issueCredential` | ~138,400 | 20 Gwei | 0.00277 ETH | Stores 32-byte `fingerprint` $\to$ `CredentialRecord` |
| `CredentialRegistry.revokeCredential` | ~34,200 | 20 Gwei | 0.00068 ETH | Updates status enum to `REVOKED` |
| `CredentialRegistry.suspendCredential` | ~32,100 | 20 Gwei | 0.00064 ETH | Updates status enum to `SUSPENDED` |
| `CredentialRegistry.reinstateCredential`| ~32,300 | 20 Gwei | 0.00065 ETH | Restores status enum to `ACTIVE` |
| `CredentialRegistry.verifyCredential` | **0 gas** | Free (Read-only) | **0.00000 ETH** | Pure view function; dynamic timestamp check |

### 5.1 Zero-Cost Dynamic Expiration Check
The smart contract evaluates expiration dynamically:
```solidity
if (cred.expirationTimestamp != 0 && block.timestamp >= cred.expirationTimestamp) {
    return (Status.EXPIRED, cred.issuer, cred.issuanceTimestamp, cred.expirationTimestamp, cred.version);
}
```
*Advantage*: Avoids keeper networks, off-chain cron bots, or periodic on-chain transactions to mark expired credentials, completely eliminating maintenance gas overhead.

---

## 6. Evaluation Limitations

1. **Sepolia Rate Limits**: Public RPC providers (such as Infura free tier) enforce rate limits (typically 100 req/sec and 25k req/day), capping sustained stress tests against live EVM nodes.
2. **Single-Worker Uvicorn Container**: The backend container was evaluated with a single async worker. In a production cluster behind an NGINX load balancer with Gunicorn Uvicorn workers (`workers = 2 * cores + 1`), local API throughput would increase linearly.
3. **WAN Latency Variance**: On-chain RPC roundtrips are subject to transatlantic internet routing latency between the host system and Infura edge points.

---

## 7. Conclusion

The performance evaluation validates that the cryptographic foundation of the system is extremely fast, with fingerprint generation taking 17.4 $\mu\text{s}$ and Merkle selective disclosure verification taking 80 $\mu\text{s}$. The primary latency component is external blockchain RPC roundtrips, which can be mitigated in production through regional nodes or read caching. All cryptographic invariants, zero-PII storage guarantees, and anti-replay mechanics operate with sub-millisecond overhead.
