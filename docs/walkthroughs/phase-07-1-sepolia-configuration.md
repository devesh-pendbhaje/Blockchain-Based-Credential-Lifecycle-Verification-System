# Phase 7.1 Walkthrough: Ethereum Sepolia Testnet Configuration & Readiness

**Project**: Blockchain-Based Credential Lifecycle Verification System  
**Repository**: `C:\Users\Sagar\Desktop\blockchain-credential-verification`  
**Phase**: 7.1 — Ethereum Sepolia Testnet Configuration  
**Execution Timestamp**: October 19, 2026  
**Status**: **PASS — READY FOR DEPLOYMENT**  

---

## 1. Executive Summary

Phase 7.1 prepares the repository for live deployment to the Ethereum Sepolia public testnet using an Infura JSON-RPC endpoint. All configuration components, environment variable definitions, credential safety barriers, and deployment scripts were inspected, harmonized, and verified.

### Key Milestones Achieved
1. **Zero Secret Exposure & Strict Git Isolation**:
   - Confirmed `.gitignore` systematically excludes all `.env` files in any repo directory (`.env`, `.env.*`), while explicitly permitting non-secret `.env.example` templates (`!.env.example`).
   - Verified via `git check-ignore -v` that `.env`, `backend/.env`, `contracts/.env`, `frontend/.env`, and `.env.local` are 100% ignored by Git.
   - Verified that no real secrets or private keys exist in version control or documentation.
2. **Harmonized Environment Variable Taxonomy**:
   - Identified the exact environment variables required by Hardhat and the FastAPI backend.
   - Updated `backend/.env.example` to maintain complete feature parity with root `.env.example`.
   - Updated `backend/app/core/config.py` to support dual env file discovery (`env_file=(".env", "../.env")`), enabling either a unified root `.env` or separate service-level `.env` files.
3. **Sepolia Network Specification (`chainId: 11155111`)**:
   - Confirmed network configuration in `contracts/hardhat.config.ts` targeting chain ID `11155111`.
   - Confirmed default chain ID alignment in `backend/app/core/config.py` and `docker-compose.yml`.
   - Verified `contracts/scripts/deploy.ts` incorporates chain ID enforcement, Mainnet guards, deployer balance checks, contract bytecode validation, and deployment manifest generation.
4. **Execution of Safe Automated Verification Suites**:
   - **Contracts**: 51/51 tests PASSED (`contracts/contracts` & `contracts/test`).
   - **Backend**: 92/92 tests PASSED (`backend/tests`), covering blockchain adapter, ABI loading, RPC sanitization, cryptographic proofs, and database lifecycle.
   - **Frontend**: 23/23 tests PASSED (`frontend/src/test`).
   - **Contract Compilation**: Verified via `npx hardhat compile`.

---

## 2. Environment Variable Specification

The following table documents the exact environment variables utilized across the Hardhat deployment tooling, backend blockchain adapter, and service containers:

| Variable Name | Required By | Format / Type | Default / Example Value | Description |
|---|---|---|---|---|
| `BLOCKCHAIN_RPC_URL` | Hardhat & Backend | HTTPS URL | `https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID` | EVM JSON-RPC endpoint. Supports Infura, Alchemy, or local node (`http://127.0.0.1:8545`). Sanitized automatically in logs. |
| `BLOCKCHAIN_CHAIN_ID` | Backend & Docker | Integer | `11155111` | EVM chain ID. Sepolia testnet is `11155111`. Local Hardhat node is `31337`. |
| `CHAIN_ID` | Backend & Hardhat | Integer | `11155111` | Backward-compatibility alias for `BLOCKCHAIN_CHAIN_ID`. Automatically harmonized in `Settings`. |
| `BLOCKCHAIN_SIGNER_PRIVATE_KEY` | Hardhat & Backend | 64 hex characters (32 bytes) | *(Leave empty until configured)* | Private key of the deployer/signer account (with or without `0x` prefix). Aliases accepted by Hardhat: `SEPOLIA_PRIVATE_KEY`, `DEPLOYER_PRIVATE_KEY`. |
| `ISSUER_REGISTRY_ADDRESS` | Backend & Docker | 42-char Hex Address | *(Populated post-deployment)* | Deployed address of `IssuerRegistry` contract on target network. |
| `CREDENTIAL_REGISTRY_ADDRESS` | Backend & Docker | 42-char Hex Address | *(Populated post-deployment)* | Deployed address of `CredentialRegistry` contract on target network. |
| `BLOCKCHAIN_TIMEOUT_SECONDS` | Backend & Docker | Float | `10.0` | HTTP JSON-RPC client request timeout in seconds. (Hardhat network timeout set to `60000` ms). |
| `CONFIRMATION_BLOCKS` | Backend & Docker | Integer | `1` | Number of block confirmations to wait for transaction finality. |
| `ETHERSCAN_API_KEY` | Hardhat | Alphanumeric | *(Optional)* | Etherscan API key for automated source code verification on Sepolia Etherscan. |
| `ENVIRONMENT` | Backend & Docker | String | `development` | Operating mode (`development`, `staging`, `production`). |
| `DATABASE_URL` | Backend | Connection URI | `postgresql+psycopg://postgres:postgres@localhost:5433/credential_verification` | PostgreSQL 16 connection string. |
| `STORAGE_ENCRYPTION_KEY` | Backend | 64 hex characters | `0123456789abcdef...` | AES-256-GCM field encryption key. |

---

## 3. Git Exclusion & Secret Protection Verification

To verify that local secrets cannot be accidentally committed or tracked, Git ignore rules were inspected and validated:

### A. Root `.gitignore` Configuration
Lines 8–10 of `.gitignore`:
```gitignore
.env
.env.*
!.env.example
```

### B. `git check-ignore` Validation Results
Command execution:
```powershell
git check-ignore -v .env backend/.env contracts/.env frontend/.env .env.local
```
Output:
```
.gitignore:8:.env    .env
.gitignore:8:.env    backend/.env
.gitignore:8:.env    contracts/.env
.gitignore:8:.env    frontend/.env
.gitignore:9:.env.*  .env.local
```

### C. Git Status Verification
`git status` reports no `.env` files tracked or staged. Only non-secret `.env.example` templates are present in the repository.

---

## 4. Sepolia Network Configuration Inspection

### A. Hardhat Configuration (`contracts/hardhat.config.ts`)
```typescript
    sepolia: {
      url: process.env.BLOCKCHAIN_RPC_URL || process.env.SEPOLIA_RPC_URL || "",
      chainId: 11155111,
      accounts: getAccounts(),
      timeout: 60000,
    },
```
- **Key Resolution**: `getAccounts()` checks `BLOCKCHAIN_SIGNER_PRIVATE_KEY`, `SEPOLIA_PRIVATE_KEY`, or `DEPLOYER_PRIVATE_KEY`. If unconfigured, it safely returns an empty array `[]` without throwing unexpected exceptions during configuration inspection.
- **Provider URL**: Dynamically reads `process.env.BLOCKCHAIN_RPC_URL` or `process.env.SEPOLIA_RPC_URL`.

### B. Deployment Automation Safeguards (`contracts/scripts/deploy.ts`)
The deployment script enforces multi-layer safety before broadcasting:
1. **Explicit Network Guard**: Rejects default or ambiguous network arguments.
2. **Chain ID Verification**: Compares connected provider chain ID with expected `11155111` for Sepolia.
3. **Ethereum Mainnet Guard**: Prevents accidental deployment to Chain ID 1 unless `ALLOW_MAINNET=true` is explicitly passed.
4. **Deployer Account & Balance Checks**: Verifies that a valid signer exists and has $> 0$ ETH balance. Provides a clear faucet instruction if balance is zero.
5. **Bytecode Verification**: Verifies `eth_getCode` $> 2$ bytes immediately following contract deployment.
6. **Manifest Generation**: Generates non-secret deployment manifests saved to `contracts/deployments/sepolia-11155111.json` and timestamped backups.

---

## 5. Modifications Applied in Phase 7.1

1. **`backend/.env.example`**:
   - Replaced outdated local-only chain defaults (`31337`) with Sepolia testnet defaults (`BLOCKCHAIN_CHAIN_ID=11155111` and `CHAIN_ID=11155111`).
   - Added Infura RPC template (`https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID`).
   - Added `BLOCKCHAIN_SIGNER_PRIVATE_KEY=` placeholder with security warning.
2. **`backend/app/core/config.py`**:
   - Updated `SettingsConfigDict` to check both `.env` (service-local) and `../.env` (workspace root):
     ```python
     model_config = SettingsConfigDict(
         env_file=(".env", "../.env"),
         env_file_encoding="utf-8",
         case_sensitive=False,
         extra="ignore",
     )
     ```
   - This ensures full interoperability whether the user creates `.env` in the workspace root or in `backend/`.

---

## 6. Safe Configuration Checks & Test Suite Results

| Test Suite | Scope / Subsystem | Total Tests | Passed | Failed | Status |
|---|---|---|---|---|---|
| **Hardhat Contracts** | Solidity contracts, Merkle proofs, multi-version traversal, key rotation | 51 | 51 | 0 | **PASS** |
| **Backend Pytest** | EVM adapter, RPC masking, ABI loading, auth, crypto, DB models | 92 | 92 | 0 | **PASS** |
| **Frontend Vitest** | UI routes, presentation workflows, credential management, health indicator | 23 | 23 | 0 | **PASS** |
| **Contract Compilation** | `npx hardhat compile` via Solc 0.8.24 viaIR | - | - | 0 | **PASS** |

---

## 7. Remaining Manual Steps for the User

Follow these steps on your local machine to deploy to Sepolia:

### Step 1: Populate Your Generated Local `.env` File
A local [.env](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/.env) file has been created at the root of the workspace with secure placeholders and confirmed to be completely ignored by Git (`.gitignore:8`).

Open [.env](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/.env) in your editor and enter:
```ini
# Replace YOUR_INFURA_PROJECT_ID with your actual Infura Sepolia API Key
BLOCKCHAIN_RPC_URL=https://sepolia.infura.io/v3/YOUR_INFURA_PROJECT_ID

# Replace with your dedicated Sepolia test-wallet private key (64 hex characters)
BLOCKCHAIN_SIGNER_PRIVATE_KEY=your_private_key_here
```

### Step 2: Ensure Your Test Wallet Has Sepolia Faucet ETH
Before running the deployment script, ensure your test account has at least `0.05` Sepolia ETH to cover gas fees. Faucets:
- [Google Cloud Web3 Sepolia Faucet](https://cloud.google.com/application/web3/faucet/ethereum/sepolia)
- [Infura Sepolia Faucet](https://www.infura.io/faucet/sepolia)
- [Sepolia PoW Faucet](https://sepolia-faucet.pk910.de/)

### Step 3: Run Safe Pre-Flight Readiness Diagnostic
Before deploying, run the read-only pre-flight diagnostic script to safely test RPC connectivity, chain ID, and account balance without broadcasting transactions or spending gas:
```bash
npx hardhat run scripts/check-sepolia.ts --network sepolia
```

### Step 4: Run the Sepolia Deployment Command
Once the diagnostic confirms account funds are ready, execute the deployment script from `contracts/` (see Section 8 below).

### Step 5: Update Deployed Contract Addresses in `.env`
After deployment completes, the deployment script will output the contract addresses and save the manifest to `contracts/deployments/sepolia-11155111.json`. Update your `.env`:
```ini
ISSUER_REGISTRY_ADDRESS=0x...
CREDENTIAL_REGISTRY_ADDRESS=0x...
```

---

## 8. Exact Next Command to Deploy to Sepolia

> [!IMPORTANT]
> **DO NOT EXECUTE THIS COMMAND** until you have added your Infura RPC URL and test-wallet private key into your local `.env` and confirmed the wallet holds Sepolia testnet ETH.

Run the following command from the `contracts/` directory:

```bash
npx hardhat run scripts/deploy.ts --network sepolia
```

*(Or from the repository root)*:
```powershell
npm --prefix contracts run hardhat run scripts/deploy.ts -- --network sepolia
```
