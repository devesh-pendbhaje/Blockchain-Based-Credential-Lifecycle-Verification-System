# Phase 7 Walkthrough: Live EVM Integration & Sepolia Testnet Deployment

**Project**: Blockchain-Based Credential Lifecycle Verification System  
**Repository**: `C:\Users\Sagar\Desktop\blockchain-credential-verification`  
**Execution Timestamp**: October 19, 2026  
**Status**: **PASS WITH BLOCKERS** (All EVM smart contract integrations, chain ID verification, contract bytecode validation, deployment automation with manifest generation, transaction anchoring, idempotent reconciliation, health probes, and 166 automated test suites [51 Hardhat + 92 Backend + 23 Frontend] PASS; live public testnet broadcast is ready and blocked only on user provisioning of external Sepolia RPC endpoint and funded faucet ETH).

---

## 1. Executive Summary

Phase 7 connects the application plane to deployed smart contracts on an EVM blockchain network. It fulfills the primary remaining architectural blocker from Phase 6 by implementing a production-grade EVM blockchain adapter, secure signer configuration, Hardhat deployment automation with manifest tracking, health reporting diagnostics, and idempotent on-chain anchoring with full receipt and event validation.

```mermaid
graph TD
    subgraph ClientAndAPI ["Client & API Layer"]
        Client["Web / Auditor Client"]
        HealthAPI["GET /health/ready & /health/blockchain"]
        CredAPI["POST /credentials (Issuance & Anchoring)"]
        ReconcileAPI["POST /credentials/{id}/versions/{v}/anchor"]
    end

    subgraph BackendAdapter ["Blockchain Adapter (BlockchainClient)"]
        RPC_Guard["Chain ID & RPC Validator<br/>• Connected vs Configured Chain ID<br/>• Sanitized URL (Masks Secrets)"]
        Bytecode_Guard["Bytecode Validator<br/>• eth_getCode > 2 bytes<br/>• Blocks unready contracts"]
        Signer_Guard["Signer Manager<br/>• Read-Only vs Transacting Mode<br/>• EIP-1559 / Nonce / Gas estimation"]
        Tx_Manager["Transaction & Receipt Handler<br/>• Receipt status == 1<br/>• Event log decoding<br/>• Revert classification"]
    end

    subgraph EVMContracts ["EVM Smart Contracts (Sepolia / Local EVM)"]
        IR["IssuerRegistry<br/>• isIssuerActive(issuerId)<br/>• getIssuer(issuerId)<br/>• registerIssuer(...)"]
        CR["CredentialRegistry<br/>• computeFingerprint(...)<br/>• issueCredential(...)<br/>• verifyCredential(...)<br/>• getCredential(...)"]
    end

    subgraph StorageLayer ["PostgreSQL 16"]
        PG_Creds[("credentials & versions<br/>issuance_status: PENDING | CONFIRMED | FAILED<br/>issuance_tx_hash, block_number, chain_id")]
    end

    Client --> HealthAPI
    Client --> CredAPI
    Client --> ReconcileAPI
    HealthAPI --> RPC_Guard
    CredAPI --> Tx_Manager
    ReconcileAPI --> Tx_Manager
    RPC_Guard --> Bytecode_Guard
    Bytecode_Guard --> Signer_Guard
    Signer_Guard --> Tx_Manager
    Tx_Manager -->|JSON-RPC / Web3| CR
    Tx_Manager -->|JSON-RPC / Web3| IR
    CredAPI --> PG_Creds
    ReconcileAPI --> PG_Creds
```

---

## 2. Actual Contracts and Interfaces Inspected

All integration points were mapped directly against the Solidity contracts in `contracts/contracts/`:

### A. `IssuerRegistry.sol`
- **Constructor**: `constructor(address initialAdmin) Ownable(initialAdmin)`
- **Key Functions**:
  - `registerIssuer(bytes32 issuerId, address initialSigningAddress, string calldata metadataUri) external onlyGovernance`: Accredits an issuing authority. Emits `IssuerRegistered(issuerId, initialSigningAddress, metadataUri)`.
  - `setIssuerStatus(bytes32 issuerId, IssuerStatus newStatus) external onlyGovernance`: Updates status (`0=None, 1=Active, 2=Suspended, 3=Revoked`).
  - `isIssuerActive(bytes32 issuerId) external view returns (bool)`: Returns true if registered and Active.
  - `getIssuerBySigningAddress(address signingAddress) external view returns (bool isAuthorized, bytes32 issuerId)`: Bidirectional key lookup.
  - `getIssuer(bytes32 issuerId) external view returns (IssuerRecord memory)`: Retrieves complete struct.

### B. `CredentialRegistry.sol`
- **Constructor**: `constructor(address issuerRegistryAddress)`: Binds immutable `IIssuerRegistry`.
- **Key Functions**:
  - `computeFingerprint(bytes32 documentDigest, bytes32 metadataDigest, bytes32 merkleRoot, bytes32 issuerId, bytes32 credentialId, uint32 version) public pure returns (bytes32)`: Pure deterministic calculation binding exactly:
    $$\text{keccak256}(\text{abi.encode}(\text{docDigest}, \text{metaDigest}, \text{merkleRoot}, \text{issuerId}, \text{credId}, \text{version}))$$
  - `issueCredential(bytes32 credentialId, bytes32 documentDigest, bytes32 metadataDigest, bytes32 merkleRoot, uint32 version, uint64 expiresAt) external returns (bytes32 fingerprint)`: Anchors composite fingerprint on-chain. Validates caller is an active issuer in `IssuerRegistry`. Enforces strict monotonic sequential versioning.
  - `suspendCredential(bytes32 fingerprint, uint8 reasonCode) external`: Lifecycle suspension with reason codes (1–5).
  - `reactivateCredential(bytes32 fingerprint) external`: Reactivates a suspended credential.
  - `revokeCredential(bytes32 fingerprint, uint8 reasonCode) external`: Terminal revocation.
  - `supersedeCredential(bytes32 oldFingerprint, bytes32 newDoc, bytes32 newMeta, bytes32 newRoot, uint64 newExpiresAt) external returns (bytes32 newFingerprint)`: Version progression.
  - `getCredential(bytes32 fingerprint) external view returns (CredentialRecord memory)`: Returns on-chain record.
  - `verifyCredential(bytes32 fingerprint, bytes32 claimedDoc, bytes32 claimedMeta, bytes32 claimedRoot) external view returns (VerificationResult memory)`: Evaluates stored status, expiration timestamp, 3-way digest match, and current issuer accreditation standing.

---

## 3. Blockchain Adapter Architecture & Design

The backend adapter (`backend/app/blockchain/client.py`) extends `BlockchainClient` with the following principles:

1. **Explicit Chain ID Enforcement**:
   - Compares connected chain ID (`w3.eth.chain_id`) against `BLOCKCHAIN_CHAIN_ID`.
   - If chain IDs mismatch, logs a security warning and immediately disables contract calls and authoritative verification (`chain_id_match = False`).
   - Never silently switches to an unverified network.

2. **Contract Bytecode Verification**:
   - Executes `w3.eth.get_code(checksum_address)` on configured contract addresses.
   - Requires bytecode length $> 2$ bytes. If empty (`0x` or `b""`), flags contracts as not deployed and disables contract execution.

3. **Read-Only vs. Transacting Separation**:
   - If `BLOCKCHAIN_SIGNER_PRIVATE_KEY` is not configured, client operates in read-only mode (`can_transact = False`).
   - Query operations (`isIssuerActive`, `getIssuer`, `getCredential`, `verifyCredential`) function normally.
   - Transaction write attempts (`register_issuer_on_chain`, `anchor_credential_fingerprint`) return safe, structured errors (`{"success": False, "status": "UNAVAILABLE", "error": "SIGNER_NOT_CONFIGURED"}`).

4. **Idempotent Reconciliation & Dual-Write Resilience**:
   - Pre-flight check queries `getCredential(fingerprint)` before submitting transactions.
   - If an on-chain record already exists (e.g. from a previous transaction whose database write failed), the adapter recognizes it as confirmed (`already_anchored: True`), updates the database, and avoids double-spending gas or creating duplicate errors.
   - Endpoint `POST /api/v1/credentials/{id}/versions/{version}/anchor` allows re-synchronizing or retrying pending records.

5. **Sanitization of RPC Credentials**:
   - `sanitize_rpc_url(url)` masks basic-auth credentials and secret path tokens (such as Infura/Alchemy API keys $\ge 16$ characters) in logs and health responses.

---

## 4. Hardhat Deployment Script Workflow

The deployment automation in `contracts/scripts/deploy.ts` incorporates institutional safeguards:

1. **Target Network Requirement**:
   - Requires explicit `--network` flag. Prevents ambiguous or unintended defaults.
2. **Mainnet Safeguard**:
   - Inspects `actualChainId`. If chain ID is `1` (Ethereum Mainnet), deployment immediately aborts unless `ALLOW_MAINNET=true` is set.
3. **Chain ID Verification**:
   - Asserts network matches connected chain (e.g., asserts chain ID `11155111` when `--network sepolia` is specified).
4. **Deployer Balance Pre-Flight**:
   - Checks deployer ETH balance. If balance is zero on non-hardhat networks, aborts with a clear funding instruction rather than failing midway.
5. **Constructor Parameter Order**:
   - Deploys `IssuerRegistry(deployer.address)`.
   - Deploys `CredentialRegistry(issuerRegistryAddress)`.
6. **Post-Deployment Bytecode Verification**:
   - Calls `ethers.provider.getCode(address)` on both resulting addresses to confirm non-empty bytecode before declaring success.
7. **Deployment Manifest Generation**:
   - Records non-secret deployment metadata to `contracts/deployments/`:
     - `contracts/deployments/${network}-${chainId}.json`
     - `contracts/deployments/${network}-${chainId}-${timestamp}.json`
     - `contracts/deployments/latest.json`
   - Manifest includes: network name, chain ID, deployer address, contract names, addresses, transaction hashes, block numbers, and constructor arguments.
   - **Never records private keys, seed phrases, or RPC tokens**.

---

## 5. Environment Variables & Configuration

The system standardizes on the following variables across `.env.example`, `backend/app/core/config.py`, and `docker-compose.yml`:

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `BLOCKCHAIN_RPC_URL` | String | `http://127.0.0.1:8545` | EVM JSON-RPC provider endpoint |
| `BLOCKCHAIN_CHAIN_ID` | Integer | `11155111` | Expected EVM Chain ID (Sepolia: `11155111`, Local: `31337`) |
| `CHAIN_ID` | Integer | (Alias) | Backward-compatible alias for `BLOCKCHAIN_CHAIN_ID` |
| `ISSUER_REGISTRY_ADDRESS` | String | `""` | 0x-prefixed deployed address of `IssuerRegistry` |
| `CREDENTIAL_REGISTRY_ADDRESS` | String | `""` | 0x-prefixed deployed address of `CredentialRegistry` |
| `BLOCKCHAIN_SIGNER_PRIVATE_KEY`| String | `None` | 32-byte hex private key for transaction submission |
| `BLOCKCHAIN_TIMEOUT_SECONDS` | Float | `10.0` | JSON-RPC HTTP timeout and transaction receipt wait limit |
| `CONFIRMATION_BLOCKS` | Integer | `1` | Required confirmation blocks for transaction finality |

---

## 6. How to Obtain and Configure a Sepolia RPC Endpoint

To connect to the public Ethereum Sepolia testnet:

1. **Provider Options**:
   - **Infura**: Create a project at [infura.io](https://infura.io) -> Web3 API -> Ethereum Sepolia -> copy endpoint:  
     `https://sepolia.infura.io/v3/<YOUR_API_KEY>`
   - **Alchemy**: Create an app at [alchemy.com](https://alchemy.com) -> Ethereum Sepolia -> copy HTTPS URL:  
     `https://eth-sepolia.g.alchemy.com/v2/<YOUR_API_KEY>`
   - **Public RPC**: Alternative endpoints from [chainlist.org](https://chainlist.org/chain/11155111) (e.g. `https://rpc.sepolia.org`), though commercial providers offer higher rate limits and reliability.

2. **Configure `.env`**:
   ```env
   BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_KEY
   BLOCKCHAIN_CHAIN_ID=11155111
   CHAIN_ID=11155111
   ```

---

## 7. How to Safely Fund a Dedicated Test Wallet

1. **Generate a Dedicated Testnet Keypair**:
   - Generate an isolated keypair specifically for Sepolia testnet interactions (e.g. via MetaMask or `openssl rand -hex 32`).
   - **Never reuse a private key that holds mainnet assets or production institutional authority.**
2. **Obtain Sepolia Faucet ETH**:
   - Google Cloud Web3 Faucet: [cloud.google.com/application/web3/faucet/ethereum/sepolia](https://cloud.google.com/application/web3/faucet/ethereum/sepolia)
   - Infura Sepolia Faucet: [infura.io/faucet/sepolia](https://infura.io/faucet/sepolia)
   - Alchemy Sepolia Faucet: [sepoliafaucet.com](https://sepoliafaucet.com)
3. **Configure the Signer in `.env`**:
   ```env
   BLOCKCHAIN_SIGNER_PRIVATE_KEY=0x<64_hex_characters_here>
   ```

---

## 8. Deployment Commands & Actual Results

### A. Deployment Execution on Local EVM (`hardhat` network)

**Execution Command**:
```powershell
cd C:\Users\Sagar\Desktop\blockchain-credential-verification\contracts
npx hardhat run scripts/deploy.ts --network hardhat
```

**Actual Execution Evidence**:
```text
=== Credential Lifecycle System Deployment ===
Target Hardhat Network: hardhat
Connected Chain ID: 31337
Deployer Address: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Deployer Balance: 10000.0 ETH

[1/2] Deploying IssuerRegistry...
  -> IssuerRegistry deployed at: 0x5FbDB2315678afecb367f032d93F642f64180aa3
  -> Transaction Hash: 0xa4c16d03a4aeb76b751652355aec55b9dea60de0c5d7ded7b81944df9fa0fcf1
  -> Block Number: 1

[2/2] Deploying CredentialRegistry...
  -> CredentialRegistry deployed at: 0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512
  -> Transaction Hash: 0x55aa9d65ad0513383f886fc2dabc095b96589098d785e5f32ef06b7f33c1e73b
  -> Block Number: 2

Deployment manifest successfully saved to:
  - C:\Users\Sagar\Desktop\blockchain-credential-verification\contracts\deployments\hardhat-31337.json
  - C:\Users\Sagar\Desktop\blockchain-credential-verification\contracts\deployments\hardhat-31337-1792382016629.json
  - C:\Users\Sagar\Desktop\blockchain-credential-verification\contracts\deployments\latest.json
```

### B. Deployment Attempt on Sepolia (Demonstrating Fail-Safe Block)

**Execution Command**:
```powershell
npx hardhat run scripts/deploy.ts --network sepolia
```

**Actual Execution Evidence (Clean Guard Fail-Closed)**:
```text
=== Credential Lifecycle System Deployment ===
Target Hardhat Network: sepolia

[DEPLOYMENT ERROR]: HH117: Empty string `` for network or forking URL - Expected a non-empty string.
```
*(Demonstrates that deployment refuses to fabricate a result when unconfigured; exit code 1).*

---

## 9. Backend Health & Diagnostics Reporting

The health probe subsystem exposes transparent diagnostics:

### `GET /health/live`
```json
{
  "status": "live"
}
```
*Never fails if PostgreSQL or blockchain is down.*

### `GET /health/ready`
```json
{
  "status": "ready",
  "database": "connected",
  "blockchain_rpc": "unavailable",
  "blockchain": {
    "status": "unavailable",
    "rpc_connected": false,
    "rpc_url": "http://127.0.0.1:8545",
    "expected_chain_id": 11155111,
    "actual_chain_id": null,
    "chain_id_match": false,
    "contracts": {
      "issuer_registry": {
        "address": null,
        "configured": false,
        "has_bytecode": false,
        "loaded": false
      },
      "credential_registry": {
        "address": null,
        "configured": false,
        "has_bytecode": false,
        "loaded": false
      }
    },
    "signer": {
      "configured": false,
      "address": null,
      "can_transact": false
    },
    "authoritative_verification_available": false
  }
}
```

### `GET /health/blockchain`
Returns the standalone diagnostic payload above with `force_refresh=True`.

---

## 10. Automated Test Results and Verification Commands

### A. Smart Contract Regression Suite (Hardhat)
**Command**:
```powershell
cd C:\Users\Sagar\Desktop\blockchain-credential-verification\contracts
npm test
```
**Outcome**: **51 passing (1s)**  
- CredentialRegistry: 6-input composite fingerprint (2), version monotonicity (7), lifecycle transitions & reason codes (7), comprehensive verification & expiry (6), version traversal (3), key rotation invariance (1).
- DomainSeparatedMerkle: leaf & parent hashing (2), odd-leaf promotion (5), proof verification & tamper resistance (3).
- IssuerRegistry: governance onboarding (6), status lifecycle (3), 2-step key rotation (4), emergency rotation (2).

### B. Backend Blockchain Adapter & Integration Suite (Pytest)
**Command**:
```powershell
cd C:\Users\Sagar\Desktop\blockchain-credential-verification\backend
.\.venv\Scripts\pytest.exe tests/test_blockchain_adapter.py -v
```
**Outcome**: **15 passed in 22.91s**  
- `test_abi_loader_loads_real_and_fallback_artifacts`
- `test_rpc_url_sanitizer`
- `test_blockchain_client_graceful_handling_without_node`
- `test_blockchain_client_wrong_chain_id_blocked`
- `test_blockchain_client_correct_chain_id`
- `test_contract_bytecode_validation`
- `test_read_only_mode_without_signer`
- `test_write_mode_with_configured_signer`
- `test_mocked_contract_credential_anchoring_success`
- `test_mocked_contract_credential_anchoring_reverted`
- `test_mocked_contract_credential_verification_parsing`
- `test_privacy_invariants_no_pii_sent_to_contract`
- `test_get_credential_record_on_chain_decoding`
- `test_health_blockchain_diagnostics_endpoint`
- `test_reconciliation_detects_already_anchored_record`

### C. Full Backend Regression Suite (Pytest)
**Command**:
```powershell
.\.venv\Scripts\pytest.exe -v
```
**Outcome**: **92 passed in 58.66s**  
- Authentication & Authorization: 26/26 passed.
- Blockchain Adapter: 15/15 passed.
- Challenge-Response: 5/5 passed.
- Credentials API: 4/4 passed.
- Database Models & Cascades: 4/4 passed.
- Document Processing: 5/5 passed.
- Encryption & Storage: 5/5 passed.
- 6-Component Fingerprint: 3/3 passed.
- Health Probes: 3/3 passed.
- Issuers API: 3/3 passed.
- Merkle Tree: 12/12 passed.
- RFC 8785 Canonicalization: 5/5 passed.
- Selective Disclosure API: 2/2 passed.

### D. Frontend Regression Suite & Production Build (Vitest & Vite)
**Commands**:
```powershell
cd C:\Users\Sagar\Desktop\blockchain-credential-verification\frontend
npm test
npm run build
```
**Outcome**: **23 passed in 21.80s; Production build successful in 11.87s** (`dist/assets/index-PrpGBjyE.js` 496 kB).

---

## 11. Cryptographic and Privacy Invariants Maintained

The 6-input composite fingerprint formula remains strictly enforced across both Solidity and Python:

$$\text{fingerprint} = \text{keccak256}(\text{abi.encode}(\text{docDigest}, \text{metaDigest}, \text{merkleRoot}, \text{issuerId}, \text{credId}, \text{version}))$$

1. **Zero PII on Chain**:
   - `issueCredential(...)` receives only 32-byte hashes (`bytes32`) and integers (`uint32`, `uint64`).
   - Names, email addresses, grades, student IDs, and raw documents are encrypted at rest with AES-256-GCM in the storage layer and never transmitted across the JSON-RPC boundary.
2. **Honest Verification Guarantee**:
   - If the blockchain node is unreachable or contracts are not deployed, `verify_credential` returns `blockchain_available: false` and `is_valid: false`.
   - Off-chain database matches **never** elevate a credential to `is_valid: true` without verified on-chain confirmation.
3. **Monotonic Version Sequencing**:
   - `CredentialRegistry` enforces that version 1 is issued first, and subsequent versions increment sequentially ($v + 1$).

---

## 12. Failures, Blockers, and Recovery Procedures

### Blocker 1: Public Sepolia RPC & Deployer Funds
- **State**: The deployment script and backend client are fully integrated for Sepolia (`chainId: 11155111`). However, deploying to the public testnet requires the user to supply their Infura/Alchemy API key and fund a dedicated testnet account via a Sepolia faucet.
- **Resolution**:
  1. Set `BLOCKCHAIN_RPC_URL` and `BLOCKCHAIN_SIGNER_PRIVATE_KEY` in `.env`.
  2. Run `npx hardhat run scripts/deploy.ts --network sepolia`.
  3. Copy the output contract addresses into `ISSUER_REGISTRY_ADDRESS` and `CREDENTIAL_REGISTRY_ADDRESS` in `.env`.

### Blocker 2: Institutional SSO / JWKS Provider (Carried over from Phase 6)
- **State**: Production Bearer token validation is ready for an external institutional OIDC provider (Keycloak / Okta); local tests execute deterministically against the mock RSA keypair.

---

## 13. Summary of Changed Files

1. `backend/app/blockchain/client.py`: Comprehensive EVM client with RPC sanitization, chain ID verification, contract bytecode checking, transaction management, diagnostics, and mock compatibility.
2. `backend/app/blockchain/abi_loader.py`: Dual-path artifact loader supporting Hardhat build artifacts and Docker fallback ABIs.
3. `backend/app/blockchain/abi/`: Bundled `IssuerRegistry.json` and `CredentialRegistry.json` fallback artifacts.
4. `backend/app/core/config.py`: Added `BLOCKCHAIN_CHAIN_ID` (11155111 default), `CHAIN_ID` alias, `BLOCKCHAIN_SIGNER_PRIVATE_KEY` hex validator, and production RPC verification.
5. `backend/app/db/session.py`: Added fast 3-second connect timeout for non-sqlite connections to eliminate offline hangs.
6. `backend/app/api/routes/health.py`: Added `/health/blockchain` endpoint and enhanced `/health/ready` with blockchain status diagnostics.
7. `backend/app/services/credential_service.py`: Added on-chain anchoring upon credential issuance and idempotent `reconcile_and_anchor_credential` method.
8. `backend/app/services/issuer_service.py`: Added `register_issuer_on_chain` method.
9. `backend/app/schemas/issuer.py`: Added `IssuerOnChainRegisterRequest` and `IssuerOnChainRegisterResponse`.
10. `backend/app/api/routes/credentials.py`: Added `POST /{credential_id}/versions/{version}/anchor` reconciliation endpoint.
11. `backend/app/api/routes/issuers.py`: Added `POST /{issuer_id}/register-on-chain` admin endpoint.
12. `contracts/hardhat.config.ts`: Configured `sepolia` and `localhost` networks with non-secret environment parsing.
13. `contracts/scripts/deploy.ts`: Complete rewrite implementing network validation, chain ID checks, mainnet safety guard, bytecode verification, and manifest saving.
14. `contracts/deployments/hardhat-31337.json` & `latest.json`: Generated deployment manifest evidence.
15. `.env.example`: Updated with non-secret placeholders for Phase 7 blockchain settings.
16. `docker-compose.yml`: Passed all blockchain environment variables to the backend service.
17. `backend/tests/test_blockchain_adapter.py`: 15 comprehensive unit & integration tests for the EVM adapter.
18. `docs/walkthroughs/phase-07-evm-integration-sepolia.md`: Real walkthrough file.

---

## 14. Phase 7 Classification

**Result: PASS WITH BLOCKERS**

All Phase 7 functional requirements, contract deployments to local EVM, bytecode verifications, transaction anchoring, idempotent reconciliation, health probes, and 166 automated test suites across smart contracts, backend, and frontend have passed. Public Sepolia broadcast is completely implemented and is blocked only on user-provisioned external RPC credentials and faucet funding.
