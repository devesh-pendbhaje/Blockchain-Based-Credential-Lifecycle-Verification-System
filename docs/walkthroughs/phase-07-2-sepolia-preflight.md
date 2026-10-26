# Phase 7.2 Walkthrough: Sepolia Pre-Flight Diagnostic & Deployment Readiness

**Project**: Blockchain-Based Credential Lifecycle Verification System  
**Repository**: `C:\Users\Sagar\Desktop\blockchain-credential-verification`  
**Phase**: 7.2 — Sepolia Pre-Flight Diagnostic and Deployment Readiness  
**Execution Timestamp**: October 19, 2026  
**Readiness Classification**: **READY FOR DEPLOYMENT**  

---

## 1. Executive Summary

Phase 7.2 executes a safe, read-only pre-flight diagnostic to verify whether the system is genuinely ready to deploy its smart contracts (`IssuerRegistry` and `CredentialRegistry`) to Ethereum Sepolia.

### Key Milestones & Findings
1. **Secret Isolation & Git Protection**:
   - Local `.env` is 100% excluded from Git (`.gitignore:8`), zero credentials or `.env` files are tracked in version control, and `.env.example` contains non-secret placeholders only.
2. **Sepolia Network Verification**:
   - Connected successfully to Ethereum Sepolia via Infura JSON-RPC.
   - Connected Chain ID confirmed: **`11155111`**.
   - Current block height queried: **`11947320`**.
3. **Wallet Derivation & Balance Verification**:
   - Derived public wallet address: **`0xf549deD49E8084bA7f6789AedDeE130296711470`**.
   - Verified live Sepolia ETH balance: **`0.03994222698442 ETH`**.
4. **Resolution of Gas Price & Fee Estimation (`0.000000032 gwei` Bug Analysis)**:
   - Identified root cause of the confusing `0.000000032 gwei` output: the previous diagnostic script conflated the EIP-1559 `maxFeePerGas` cap (which is $15 \times 2 + 2 = 32$ wei on testnet) with the legacy `gasPrice`, and formatted 32 wei using unit `gwei` without indicating wei.
   - Created [contracts/scripts/fee-utils.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/scripts/fee-utils.ts) to strictly distinguish `baseFeePerGas`, `maxPriorityFeePerGas`, `maxFeePerGas`, and `gasPrice`.
   - Implemented wei-safe BigInt arithmetic for deployment cost estimation and cost cap calculations.
   - Added 15 comprehensive unit tests in [contracts/test/FeeEstimation.test.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/test/FeeEstimation.test.ts); all 66 contract & fee tests **PASSED**.
5. **Final Status**: **`READY FOR DEPLOYMENT`**. Deployer account has verified testnet funds that exceed the required gas costs.

---

## 2. Root Cause Analysis: The `0.000000032 gwei` Output

### What Happened
In earlier runs, `check-sepolia.ts` displayed:
```
[INFO] Current Gas Price: 0.000000032 gwei
```

### Technical Cause
1. **EIP-1559 vs. Legacy Gas Conflation**:
   Ethers `provider.getFeeData()` returns a `FeeData` object containing:
   - `gasPrice`: legacy gas price estimate from `eth_gasPrice` (~17 wei on Sepolia).
   - `maxFeePerGas`: EIP-1559 transaction fee cap computed by ethers as $2 \times \text{baseFee} + \text{maxPriorityFeePerGas}$ (32 wei).
   - `maxPriorityFeePerGas`: miner tip (2 wei).
   - Latest block `baseFeePerGas`: protocol base fee (15 wei).
   The previous script did:
   ```typescript
   const gasPrice = feeData.maxFeePerGas || feeData.gasPrice || ...;
   console.log(`Current Gas Price: ${ethers.formatUnits(gasPrice, "gwei")} gwei`);
   ```
   This labeled `maxFeePerGas` (a cap, not a price) as "Current Gas Price".
2. **Sub-Gwei Unit Formatting**:
   On Ethereum Sepolia, network traffic is currently low, causing base fees to drop to double-digit **wei** (15 wei). Formatting 32 wei using the `"gwei"` ($10^9$ wei) unit produced:
   $$\frac{32}{10^9} = 0.000000032 \text{ gwei}$$
   Without displaying integer wei, this decimal representation appeared abnormal.
3. **Fabricated Fallback Removed**:
   The previous script contained a fallback that assigned `0.05 ETH` when gas estimation failed. This was eliminated: fee data is now strictly parsed, and if missing, cost estimation is marked as unavailable.

---

## 3. Fee Breakdown & Wei-Safe Arithmetic Implementation

The modular fee calculation engine [contracts/scripts/fee-utils.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/scripts/fee-utils.ts) implements the following rules:

### A. Fee Metrics Distinction
```typescript
// EIP-1559 calculation
const effectiveRate = baseFee + maxPriorityFeePerGas; // 15 + 2 = 17 wei
const maxFeeCap = maxFeePerGas;                       // 32 wei
```

### B. Wei-Safe BigInt Arithmetic
```typescript
const expectedCostWei = totalGas * effectiveRate;
const maxCostWei = totalGas * maxFeeCap;

const expectedCostEth = ethers.formatEther(expectedCostWei);
const maxCostEth = ethers.formatEther(maxCostWei);
```

### C. Live Sepolia Fee Metrics Output
```
--- Fee Metrics Breakdown ---
  Fee Model: EIP-1559
  Block Base Fee: 15 wei (0.000000015 gwei)
  Max Priority Fee (Tip): 2 wei (0.000000002 gwei)
  Max Fee Per Gas (Cap): 32 wei (0.000000032 gwei)
  Reported gasPrice: 17 wei (0.000000017 gwei)
  Effective Rate Used for Expected Cost: 17 wei (0.000000017 gwei)
  Rate Basis: Base fee (15 wei) + priority fee (2 wei)
```

---

## 4. Live Diagnostic Command Execution Results

Command executed from `contracts/`:
```bash
npx hardhat run scripts/check-sepolia.ts --network sepolia
```

### Actual Output:
```
=================================================
Phase 7.2 — Sepolia Pre-Flight Readiness Diagnostic
=================================================
Target Hardhat Network: sepolia
RPC Provider URL: https://sepolia.infura.io/v3/***

[CHECK 1] RPC URL Configured: PASS
[CHECK 2] Test Wallet Key Format: PASS (32 bytes / 64 hex characters)
[CHECK 3] Derived Public Address: 0xf549deD49E8084bA7f6789AedDeE130296711470

--- Deployment Script Safeguards Audit ---
[CHECK 4] Mainnet Safeguard: PASS (deploy.ts explicitly reverts on Chain ID 1 unless ALLOW_MAINNET=true)
[CHECK 5] Network Parity Guard: PASS (deploy.ts validates connected chain ID == 11155111 for sepolia)
[CHECK 6] Deployment Manifest Logic: PASS (records network, chainId, blockNumber, and contract addresses to deployments/)

--- Network Connectivity & Chain ID ---
[CHECK 7] RPC Endpoint Reachable: PASS
[CHECK 8] Connected Chain ID: 11155111
[CHECK 9] Chain ID Parity: PASS (Confirmed Ethereum Sepolia Testnet 11155111)
[INFO] Current Sepolia Block Height: 11947320

--- Test Wallet Balance & Gas Estimation ---
[CHECK 10] Wallet Sepolia ETH Balance: 0.03994222698442 ETH

--- Fee Metrics Breakdown ---
  Fee Model: EIP-1559
  Block Base Fee: 15 wei (0.000000015 gwei)
  Max Priority Fee (Tip): 2 wei (0.000000002 gwei)
  Max Fee Per Gas (Cap): 32 wei (0.000000032 gwei)
  Reported gasPrice: 17 wei (0.000000017 gwei)
  Effective Rate Used for Expected Cost: 17 wei (0.000000017 gwei)
  Rate Basis: Base fee (15 wei) + priority fee (2 wei)

--- Estimated Deployment Gas & Cost ---
  Estimated Gas for IssuerRegistry: 6153710 units
  Estimated Gas for CredentialRegistry: 10758493 units
  Total Estimated Gas: 16912203 units
  [APPROXIMATE] Expected Cost: ~0.000000000287507451 Sepolia ETH (287507451 wei)
  [APPROXIMATE] Maximum Cost Cap: ~0.000000000541190496 Sepolia ETH (541190496 wei)
  * Note: Estimates are approximate based on current network base fee and priority fee.

=================================================
READINESS CLASSIFICATION: READY FOR DEPLOYMENT
=================================================

Deployer wallet balance (0.03994222698442 ETH) meets or exceeds the estimated deployment cost (expected: ~0.000000000287507451 ETH, cap: 0.000000000541190496 ETH).
All pre-flight checks PASSED. Ready to execute contract deployment!
```
Exit Code: `0`.

---

## 5. Automated Test Suite Results

Command:
```bash
npm test (in contracts/)
```

Output:
```
  CredentialRegistry Contract: 22 passed
  DomainSeparatedMerkle Library: 11 passed
  Fee Estimation & Gas Cost Utilities: 15 passed
  IssuerRegistry Contract: 18 passed

  66 passing (1s)
```
All 66 tests PASSED with zero errors or warnings.

---

## 6. Files Modified or Created

1. **[contracts/scripts/fee-utils.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/scripts/fee-utils.ts)** *(Created)*:
   - Module providing `formatFeeValue`, `parseFeeMetrics`, `calculateDeploymentCost`, and `evaluateBalanceReadiness`.
   - Enforces wei-safe BigInt arithmetic and eliminates fabricated fallback values.
2. **[contracts/scripts/check-sepolia.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/scripts/check-sepolia.ts)** *(Updated)*:
   - Integrated `fee-utils.ts` for structured fee reporting, distinguishing EIP-1559 base fee, priority fee, max fee cap, and legacy gas price.
   - Retains 100% read-only operation: no transactions, no deployments, no gas spent.
3. **[contracts/test/FeeEstimation.test.ts](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/contracts/test/FeeEstimation.test.ts)** *(Created)*:
   - 15 unit tests covering fee formatting, EIP-1559 parsing, legacy parsing, BigInt math, missing fee handling, and balance evaluation.
4. **[docs/walkthroughs/phase-07-2-sepolia-preflight.md](file:///c:/Users/Sagar/Desktop/blockchain-credential-verification/docs/walkthroughs/phase-07-2-sepolia-preflight.md)** *(Updated)*:
   - Documented the `0.000000032 gwei` root cause, live Sepolia diagnostic execution, test results, and deployment readiness.

---

## 7. Exact Next Command to Deploy to Sepolia

All pre-flight checks have passed, the deployer wallet holds verified testnet funds, and the deployment script safeguards are active.

When you are ready to deploy your smart contracts to Sepolia, execute:

```bash
npx hardhat run scripts/deploy.ts --network sepolia
```

*(Or from repository root)*:
```powershell
npm --prefix contracts run hardhat run scripts/deploy.ts -- --network sepolia
```
