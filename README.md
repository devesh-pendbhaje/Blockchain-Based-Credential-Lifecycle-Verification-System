# Blockchain-Based Credential Lifecycle Verification System

An industry-oriented, decentralized credential issuance, lifecycle management, and verification framework built on modern cryptographic principles and public/consortium distributed ledgers.

---

## 1. Executive Summary & Purpose

Traditional educational, corporate, and professional credentials suffer from vulnerability to forgery, high verification latency, central points of failure, and excessive disclosure of personal identifiable information (PII). 

This platform provides an **enterprise-ready, privacy-preserving credential verification architecture** where:
- **Issuers** (e.g., universities, certifying bodies, corporations) issue cryptographically provable credentials anchored to a blockchain registry.
- **Holders** (students, professionals, employees) hold their verifiable credentials and control how their data is presented.
- **Verifiers** (employers, regulatory authorities, partner institutions) authenticate credentials instantly, trustlessly, and mathematically without intermediary delays or vendor lock-in.

---

## 2. Core Methodological Pillars

The platform is designed around six foundational engineering and cryptographic principles:

1. **Cryptographic Credential Fingerprints & Salted Merkle Leaves**:
   - Structured claims are blinded with 256-bit cryptographically secure salts and arranged into a Merkle tree.
   - Only the 32-byte Merkle root digest is registered on-chain.
   - **Strict Zero-PII Policy**: Complete certificates, plaintext metadata, and personal identifiable information are **never** stored on the public blockchain, guaranteeing GDPR compliance and permanent data privacy.

2. **Authenticated Issuer Registry**:
   - An on-chain identity registry maintains verified public keys and decentralized identifiers (DIDs) of accredited issuing authorities.
   - Unauthorized addresses cannot anchor or revoke credentials under an accredited organization's identifier.

3. **Complete Credential Lifecycle Management**:
   - Supports the full operational state machine of a credential: `Active`, `Suspended`, `Revoked`, and dynamic `Expired` evaluation.
   - On-chain storage is gas-optimized with dynamic block-timestamp expiration lookups, avoiding costly periodic keeper transactions.
   - Revocation registries support immediate cryptographic invalidation with immutable audit trails.

4. **Protected Off-Chain Storage**:
   - Raw certificate documents and structured credentials reside in secure, protected off-chain storage (AES-256-GCM encrypted local storage for local development, swappable for IPFS).
   - Tamper-proofing is achieved because any modification to the off-chain payload changes its hash, failing on-chain fingerprint matching.

5. **Verifier-Specific Nonce / Challenge-Response Protocol**:
   - Presentation proofs use a challenge-response handshake involving a dynamic, short-lived nonce issued by the verifier.
   - Prevents credential presentation replay attacks and presentation cloning.

6. **Selective Disclosure with Dictionary-Attack Protection**:
   - Employs Merkle sub-tree proofs across salted individual credential attributes.
   - High-entropy blinding salts ($2^{256}$ search space) prevent verifiers from brute-forcing undisclosed attributes via rainbow tables.
   - Enables a holder to prove specific claims (e.g., "Graduated with honors", "Degree = Computer Science") without revealing grades, birth dates, or home addresses.

---

## 3. System Architecture & Components

The repository is structured into distinct, decoupled subsystems:

```
blockchain-credential-verification/
├── backend/                  # Application layer & cryptographic service engine
│   ├── app/
│   │   ├── api/              # RESTful API route definitions (v1)
│   │   ├── blockchain/       # Web3 contract connectors, provider handlers & event listeners
│   │   ├── core/             # Application configuration, settings & security middleware
│   │   ├── crypto/           # Hashing, Merkle tree generation, digital signature routines
│   │   ├── models/           # ORM database entity definitions
│   │   ├── schemas/          # Data validation schemas (Pydantic / DTOs)
│   │   ├── services/         # Domain business logic (Issuance, Verification, Audit)
│   │   └── storage/          # Off-chain storage adapters (Encrypted IPFS / Cloud Storage)
│   └── tests/                # Backend unit and service test suites
├── contracts/                # Smart contracts layer (Ethereum / EVM-compatible)
│   ├── scripts/              # Contract compilation, deployment, and configuration scripts
│   └── test/                 # Smart contract unit tests (Gas benchmarking, assertion tests)
├── database/                 # Off-chain persistence schemas, migrations, and seeds
├── docs/                     # Architectural, cryptographic, and threat model documentation
│   ├── architecture/         # System design, interaction diagrams, data schemas
│   ├── experiments/          # Gas efficiency and latency benchmarks
│   └── threat-model/         # Security threat vectors and risk mitigation analysis
├── frontend/                 # Client interfaces (Portals for Issuers, Holders, Verifiers)
├── scripts/                  # Repository management, CI/CD orchestration, local dev scripts
└── tests/
    └── integration/          # Multi-component end-to-end integration test scenarios
```

---

## 4. Planned Development Stages

Development follows a structured 5-phase engineering progression:

| Phase | Milestone | Scope | Status |
| :--- | :--- | :--- | :--- |
| **Phase 1** | **Smart Contracts Core** | `IssuerRegistry.sol`, `CredentialRegistry.sol`, `DomainSeparatedMerkle.sol`, 6-input fingerprinting, and 51 Hardhat unit tests. | **COMPLETED** |
| **Phase 2** | **Backend API & Database Foundation** | FastAPI app, PostgreSQL models, Alembic migrations, 6-input cross-language parity, Docker Compose, and 17 Pytest tests. | **COMPLETED** |
| **Phase 3** | **Cryptographic Storage & Selective Disclosure** | Off-chain encrypted certificate storage, salted Merkle tree generation, and verifier challenge-response handshake (53 Pytest tests). | **COMPLETED** |
| **Phase 4** | **Frontend Portals & API Integration** | React, TypeScript, and Vite interfaces for Issuers, Holders, and Verifiers (23 Vitest tests, strict TS, zero secret persistence). | **COMPLETED** |
| **Phase 5** | **Integration, Security & Audit** | End-to-end integration workflows, gas benchmarking, and containerized deployment. | Planned |

---

## 5. Security & Privacy Guarantees

- **No On-Chain PII**: Complete certificates, personal identity details, and raw attributes are strictly excluded from on-chain storage and event logs.
- **Cryptographic Immutability**: Any alteration to a certificate breaks mathematical hash parity with the 6-input fingerprint anchored on-chain.
- **Second-Preimage Resistance**: The custom Merkle tree implementation uses domain separators (`0x00` for leaves, `0x01` for internal nodes) and odd-leaf promotion.
- **Honest Verification Boundary**: The backend and frontend never fabricate valid status based on database records alone; they explicitly mark blockchain verification as incomplete/unavailable when the node is unreachable.
- **Zero Browser Secret Persistence**: No plaintext certificates, decrypted files, private keys, or blinding salts are stored in `localStorage` or `sessionStorage`.
- **Provenance Permanence**: Key rotation updates signing keys without mutating or invalidating historical credentials.

---

## 6. Developer Setup & Reproduction Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- Docker and Docker Compose (optional for PostgreSQL containerization)

### 1. Smart Contracts Subsystem (Hardhat)
Compile contracts and run the 51 automated unit tests:
```powershell
cd contracts
npm install
npx hardhat compile
npm test
cd ..
```

### 2. Backend Subsystem (FastAPI & PostgreSQL)
Initialize the virtual environment and install dependencies:
```powershell
python -m venv backend\.venv
backend\.venv\Scripts\pip.exe install -r backend\requirements.txt
```

Run Alembic schema migrations:
```powershell
# Offline SQL generation (no active DB needed):
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head --sql

# Live migration to PostgreSQL:
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head
```

Run the backend automated Pytest suite (53 tests):
```powershell
backend\.venv\Scripts\pytest.exe -v backend\tests
```

Start the FastAPI application locally:
```powershell
backend\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --reload --port 8000
```
- Interactive OpenAPI Docs: `http://localhost:8000/api/v1/docs`
- Liveness Probe: `http://localhost:8000/health/live`
- Readiness Probe: `http://localhost:8000/health/ready`

### 3. Frontend Subsystem (React, TypeScript & Vite)
Install dependencies and run frontend development server:
```powershell
cd frontend
npm install
npm run dev
```
- Frontend Application: `http://localhost:5173`

Run frontend strict type checking and automated tests (23 tests):
```powershell
# Strict TypeScript check:
npm run lint

# Vitest test suite:
npm test

# Production bundle build:
npm run build
cd ..
```

### 4. Running the Complete Stack with Docker Compose
To run PostgreSQL 16, FastAPI backend, and React frontend containers together:
```powershell
docker compose up --build -d
```
- PostgreSQL is mapped to port `5433` on the host to avoid colliding with default port `5432`.
- Backend runs at `http://localhost:8000`.
- Frontend runs at `http://localhost:5173`.

---

## 7. Reviewable Implementation Walkthroughs

Detailed walkthroughs for each development phase are preserved under `docs/walkthroughs/` and appear in the IDE's Review panel:
- Phase 1 (Smart Contracts): [`docs/walkthroughs/phase-01-smart-contracts.md`](docs/walkthroughs/phase-01-smart-contracts.md)
- Phase 2 (Backend & Database): [`docs/walkthroughs/phase-02-backend-database.md`](docs/walkthroughs/phase-02-backend-database.md)
- Phase 3 (Cryptography & Storage): [`docs/walkthroughs/phase-03-cryptography-storage-challenge-response.md`](docs/walkthroughs/phase-03-cryptography-storage-challenge-response.md)
- Phase 4 (Frontend & API Integration): [`docs/walkthroughs/phase-04-frontend-api-integration.md`](docs/walkthroughs/phase-04-frontend-api-integration.md)


