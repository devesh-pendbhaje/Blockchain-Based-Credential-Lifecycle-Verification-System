# Blockchain-Based Credential Lifecycle Verification System

An industry-oriented, decentralized credential issuance, lifecycle management, and verification framework built on modern cryptographic principles and public/consortium distributed ledgers.

---

## 1. Executive Summary & Purpose

Traditional educational, corporate, and professional credentials suffer from vulnerability to forgery, high verification latency, central points of failure, and excessive disclosure of personal identifiable information (PII).

This project implements a **functional, privacy-preserving credential verification architecture prototype** where:
- **Issuers** (e.g., universities, certifying bodies, corporations) issue cryptographically provable credentials anchored to an EVM blockchain registry.
- **Holders** (students, professionals, employees) hold their verifiable credentials and control how their claims are presented.
- **Verifiers** (employers, regulatory authorities, partner institutions) authenticate credentials instantly and cryptographically without intermediary delays or vendor lock-in.

---

## 2. Core Methodological Pillars

The platform is designed around six foundational engineering and cryptographic principles:

1. **Cryptographic Credential Fingerprints & Salted Merkle Leaves**:
   - Structured claims are blinded with 256-bit cryptographically secure salts and arranged into a domain-separated Merkle tree.
   - Only the 32-byte Merkle root digest is registered on-chain.
   - **Zero-PII Storage**: Complete certificates, plaintext metadata, and personal identifiable information are **never** stored on the public blockchain, mitigating public PII exposure.

2. **Authenticated Issuer Registry**:
   - An on-chain identity registry maintains verified public keys and identifiers of accredited issuing authorities.
   - Unauthorized signing wallets cannot anchor or revoke credentials under an accredited organization's identifier.

3. **Complete Credential Lifecycle Management**:
   - Supports the full operational state machine of a credential: `Active`, `Suspended`, `Revoked`, and dynamic `Expired` evaluation.
   - On-chain storage is gas-optimized with dynamic block-timestamp expiration lookups, avoiding costly periodic keeper transactions.
   - Revocation registries support immediate cryptographic invalidation with immutable audit trails.

4. **Protected Off-Chain Storage**:
   - Raw certificate documents and structured credentials reside in secure off-chain storage (AES-256-GCM encrypted local storage for local development, swappable for cloud storage).
   - Key rotation is supported via fallback decryption keys (`STORAGE_PREVIOUS_ENCRYPTION_KEYS`) and automatic re-encryption under the primary key.
   - Tamper-proofing is achieved because any modification to the off-chain payload changes its hash, failing on-chain fingerprint matching.

5. **Verifier-Specific Nonce / Challenge-Response Protocol**:
   - Presentation proofs use a challenge-response handshake involving a dynamic, short-lived nonce issued by the verifier.
   - Atomically consumed on presentation to prevent credential presentation replay attacks and presentation cloning.

6. **Selective Disclosure with Dictionary-Attack Protection**:
   - Employs Merkle sub-tree proofs across salted individual credential attributes.
   - High-entropy blinding salts ($2^{256}$ search space) prevent verifiers from brute-forcing undisclosed attributes via rainbow tables.
   - Enables a holder to prove specific claims (e.g., "Degree = Computer Science") without revealing sensitive attributes such as national ID numbers or grades.

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
│   │   └── storage/          # Off-chain storage adapters (Encrypted Filesystem / Cloud Storage)
│   └── tests/                # Comprehensive unit, regression, and E2E test suites
├── contracts/                # Smart contracts layer (Ethereum / EVM-compatible, 72 Hardhat tests)
│   ├── contracts/            # CredentialRegistry.sol, IssuerRegistry.sol, DomainSeparatedMerkle.sol
│   ├── scripts/              # Contract compilation, deployment, and configuration scripts
│   └── test/                 # Smart contract unit tests
├── database/                 # Off-chain persistence schemas, migrations, and seeds
├── docs/                     # Architectural, cryptographic, threat model, and security documentation
│   ├── architecture/         # System design, interaction diagrams, data schemas
│   ├── security/             # Encryption key management & rotation guide
│   └── threat-model/         # Security threat vectors and risk mitigation analysis
├── frontend/                 # Client interfaces (React, TypeScript, Vite)
├── scripts/                  # Repository management, CI/CD orchestration, local dev scripts
└── run.ps1 / run.sh          # Local dev startup orchestrators (bind to 127.0.0.1)
```

---

## 4. Security & Hardening Features

- **Fail-Closed Verification**: Presentation verification strictly fails closed (`overall_valid=false`) if any gate fails (Merkle proof, challenge nonce replay, fingerprint binding, or on-chain status). When the blockchain node is unreachable, the system displays an explicit `UNAVAILABLE` status rather than claiming validity.
- **Tenant & Issuer Authorization**: Issuers can only create and manage versions for credentials they own; cross-tenant version creation is rejected before any database mutation. Unbound issuers and non-admin users are denied access to issuer operations.
- **Strict Key Management**: In production, missing or known example encryption keys are rejected on startup. Key rotation is supported without downtime via fallback decryption keys. See [`docs/security/encryption-key-management.md`](docs/security/encryption-key-management.md).
- **Environment Isolation**: Dev-only auth endpoints and simulated signing keys are strictly disabled unless `AUTH_MODE=local_dev` and `ENVIRONMENT=development` (or `test`). Dev services bind exclusively to loopback (`127.0.0.1`).
- **Sovereign Holder Packages**: Credentials export complete encrypted packages with attributes and salts. Re-generating salts for already-anchored credentials is prohibited, and reconstructed Merkle roots are validated against the issued record.
- **Zero Browser Secret Persistence**: No plaintext certificates, decrypted files, private keys, or blinding salts are stored in `localStorage` or `sessionStorage`.

---

## 5. Local quick start

The default runner starts a complete **local development system**: Hardhat chain 31337,
deployed issuer/credential contracts, a registered demo issuer, fresh SQLite database,
encrypted document storage, FastAPI, and React. It does not use public-chain funds or
change your existing `.env`. Services bind to `127.0.0.1`.

Install once (Python 3.10+ and a supported Node.js version are required):

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
npm ci --prefix contracts
npm ci --prefix frontend
```

From the project folder in Antigravity's terminal:

```powershell
.\run.ps1 start
```

Wait for `READY`, then open **http://127.0.0.1:5173**. API documentation is at
http://127.0.0.1:8000/api/v1/docs. Keep the terminal running. In another terminal:

```powershell
.\run.ps1 status
.\run.ps1 stop
```

If PowerShell execution policy blocks the script, use
`backend/.venv/Scripts/python.exe -u scripts/local_stack.py start`.
Git Bash/Linux/macOS: `bash run.sh start` (use `backend/.venv/bin/python` for setup).
Ports can be changed with `scripts/local_stack.py start --api-port 8001 --ui-port 5174 --rpc-port 8546`.

**Session lifetime:** every start creates a fresh local blockchain and matching database.
Previous encrypted files/databases remain in `data/local/<session>` for inspection; their
credentials belong to the old chain and cannot be verified against the new session.
The runner refuses occupied ports instead of stopping unrelated programs.
`data/local/current.json` identifies the current session. Its `environment.json` contains
local development keys: keep it private and retain it with the encrypted files.

### Try the full workflow

1. Click **Sign In**, choose the local **Issuer** persona, and open **Credential Issuance**.
   The seeded issuer ID and a new credential ID are filled automatically. Upload a test
   PDF, canonicalize metadata, build the salted attribute tree, and issue the credential.
2. After confirmation, export an encrypted holder package using a passphrase of at least
   12 characters. Send the file and passphrase separately to the holder.
3. Sign in as **Verifier**, open **Selective Disclosure**, create and download a challenge.
4. Sign in as **Holder** before importing. In **Holder Wallet**, unlock the encrypted
   package. Click **Present selected claims**, import the verifier challenge, explicitly
   select claims, generate, and download the presentation.
5. Sign back in as the **same Verifier**. Import the presentation in step 3 and verify.
   Challenges expire after five minutes and can be consumed once. A replay needs a new
   challenge. Identity changes clear decrypted packages from memory.
6. As the issuer, use **Credential Lifecycle** to suspend/reactivate/revoke or reconcile
   a pending transaction. Public verification uses the fingerprint, without authentication.

For a repeatable demonstration and a ready-made fictional holder package:

```powershell
backend/.venv/Scripts/python.exe scripts/verify_local_e2e.py
```

This sends real HTTP requests and real transactions to the local deployed contracts.
It covers upload, issuance, idempotency, disclosure, replay rejection, suspension,
reactivation, supersession, and revocation. The output identifies an active demo
fingerprint and encrypted `demo-holder.credential`; its demo passphrase is
`local-demo-passphrase`. This is fictional test data only.

### Automated checks

```powershell
# Isolate backend tests from any configured public RPC/signer:
$env:BLOCKCHAIN_RPC_URL='http://127.0.0.1:1'
$env:BLOCKCHAIN_SIGNER_PRIVATE_KEY=''
$env:BLOCKCHAIN_TIMEOUT_SECONDS='0.2'
$env:ENVIRONMENT='development'
$env:AUTH_MODE='local_dev'
backend/.venv/Scripts/python.exe -m pytest backend/tests -q
npm --prefix frontend test -- --maxWorkers=2 --minWorkers=1
npm --prefix frontend run build
cd contracts
node node_modules/hardhat/internal/cli/cli.js --config hardhat.local.config.ts test
cd ..
```

API tests use explicitly identified chain doubles where needed; the separate local
end-to-end script exercises the real EVM. The frontend build also checks TypeScript.

### Existing deployments and operational limits

The local demo is not a production deployment. For an existing PostgreSQL database,
back up first, configure the intended database/environment, and run from `backend/`:
`python -m alembic upgrade head`. Migration `20261027_0005` adds durable transaction
operations. The local runner creates tables only in its brand-new SQLite session.
PostgreSQL migration SQL has been generated and checked; an external production
PostgreSQL migration has not been executed here.

Run **one API signing worker**. Current transaction/nonce serialization is process-local;
multiple signing workers require a shared queue/lock. Do not independently submit
transactions from another process with the same signer. Intent and signed transaction
hash are committed before broadcast. A timeout leaves the operation `SUBMITTED`;
reconciliation checks that hash and does not blindly resend. A permanently dropped
transaction needs operator investigation; there is no automatic fee replacement.
Pending supersession keeps the old version current until the complete new on-chain
record is confirmed. RPC outages never produce an authoritative VALID result.

For production, configure OIDC (HTTPS issuer/audience/JWKS), a registered issuer signer,
real contract addresses, durable PostgreSQL and storage, backups, TLS, and non-example
256-bit storage keys. Local personas are disabled outside development/test. Existing
`.env` settings are not modified by the local launcher. Browser packages use
PBKDF2-SHA256 (310,000 iterations) and AES-256-GCM; plaintext attributes and original
salts are held only in memory, not browser history or browser storage. Proof generation
currently sends the full package to the authenticated backend; this is not a fully
client-side cryptography system. Merkle proofs establish issued claims, not ownership
of the presenter identity.

---

## 6. Reviewable Implementation Walkthroughs

Detailed walkthroughs for development phases and security implementations:
- Authentication & Local Setup: [`docs/walkthroughs/authentication-local-setup.md`](docs/walkthroughs/authentication-local-setup.md)
- Key Management & Rotation: [`docs/security/encryption-key-management.md`](docs/security/encryption-key-management.md)
- Phase 1 (Smart Contracts): [`docs/walkthroughs/phase-01-smart-contracts.md`](docs/walkthroughs/phase-01-smart-contracts.md)
- Phase 2 (Backend & Database): [`docs/walkthroughs/phase-02-backend-database.md`](docs/walkthroughs/phase-02-backend-database.md)
- Phase 3 (Cryptography & Storage): [`docs/walkthroughs/phase-03-cryptography-storage-challenge-response.md`](docs/walkthroughs/phase-03-cryptography-storage-challenge-response.md)
- Phase 4 (Frontend & API Integration): [`docs/walkthroughs/phase-04-frontend-api-integration.md`](docs/walkthroughs/phase-04-frontend-api-integration.md)
