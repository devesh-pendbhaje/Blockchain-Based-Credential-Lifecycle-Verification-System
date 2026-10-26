import { ethers, network } from "hardhat";
import * as fs from "fs";
import * as path from "path";
import { runPreflightValidation } from "./fee-utils";

async function main() {
  console.log("=== Credential Lifecycle System Deployment ===");
  console.log(`Target Hardhat Network: ${network.name}`);

  // 1. Fetch network provider and verify connected chain ID
  const provider = ethers.provider;
  const netInfo = await provider.getNetwork();
  const actualChainId = Number(netInfo.chainId);
  console.log(`Connected Chain ID: ${actualChainId}`);

  // 2. Resolve deployer account
  const signers = await ethers.getSigners();
  if (!signers || signers.length === 0) {
    throw new Error(
      `DEPLOYMENT BLOCKED: No deployer account configured for network '${network.name}'. Set BLOCKCHAIN_SIGNER_PRIVATE_KEY or SEPOLIA_PRIVATE_KEY in .env.`
    );
  }
  const deployer = signers[0];
  console.log(`Deployer Address: ${deployer.address}`);

  // 3. Resolve contract factories
  const IssuerRegistryFactory = await ethers.getContractFactory("IssuerRegistry");
  const CredentialRegistryFactory = await ethers.getContractFactory("CredentialRegistry");

  // 4. Execute Mandatory Preflight Validation (BEFORE ANY TRANSACTION IS BROADCAST)
  console.log("\n--- Executing Pre-Flight Safety Validation ---");
  const preflight = await runPreflightValidation(
    provider,
    deployer,
    {
      actualChainId,
      targetNetwork: network.name,
      allowMainnet: process.env.ALLOW_MAINNET === "true",
      safetyMarginPercent: 25n, // 25% conservative safety buffer
    },
    IssuerRegistryFactory,
    CredentialRegistryFactory
  );

  console.log(`[PASS] Chain ID & Mainnet Guard Verified (Chain ID: ${actualChainId})`);
  console.log(`[PASS] Predicted IssuerRegistry Address: ${preflight.predictedIssuerRegistryAddress}`);
  console.log(`[PASS] Total Estimated Deployment Gas: ${preflight.totalGas.toString()} units`);
  console.log(`[PASS] Expected Deployment Cost: ~${preflight.expectedCostEth} ETH (${preflight.expectedCostWei.toString()} wei)`);
  console.log(`[PASS] Maximum Cost Cap: ~${preflight.maxCostEth} ETH (${preflight.maxCostWei.toString()} wei)`);
  console.log(`[PASS] Conservative Cost (${preflight.safetyMarginPercent.toString()}% margin): ~${preflight.conservativeCostEth} ETH (${preflight.conservativeCostWei.toString()} wei)`);
  console.log(`[PASS] Deployer Balance: ${preflight.balanceEth} ETH (${preflight.balanceWei.toString()} wei)`);
  console.log(`[PASS] Balance Check: Deployer has sufficient funds for conservative deployment cap.`);
  console.log(`[PASS] Explicit Fee Overrides:`, preflight.feeOverrides);

  // 5. Deploy IssuerRegistry contract with deployer as initial governance admin
  console.log("\n[1/2] Deploying IssuerRegistry...");
  const issuerRegistry = await IssuerRegistryFactory.deploy(
    deployer.address,
    preflight.feeOverrides
  );
  await issuerRegistry.waitForDeployment();
  const issuerRegistryAddress = await issuerRegistry.getAddress();
  const irDeployTx = issuerRegistry.deploymentTransaction();
  const irReceipt = await irDeployTx?.wait();

  // Verify contract bytecode presence
  const irBytecode = await provider.getCode(issuerRegistryAddress);
  if (!irBytecode || irBytecode === "0x" || irBytecode.length <= 2) {
    throw new Error(`IssuerRegistry deployment failed: no contract bytecode found at ${issuerRegistryAddress}`);
  }
  console.log(`  -> IssuerRegistry deployed at: ${issuerRegistryAddress}`);
  console.log(`  -> Transaction Hash: ${irDeployTx?.hash}`);
  console.log(`  -> Block Number: ${irReceipt?.blockNumber}`);

  // 6. Deploy CredentialRegistry referencing IssuerRegistry address
  console.log("\n[2/2] Deploying CredentialRegistry...");
  const credentialRegistry = await CredentialRegistryFactory.deploy(
    issuerRegistryAddress,
    preflight.feeOverrides
  );
  await credentialRegistry.waitForDeployment();
  const credentialRegistryAddress = await credentialRegistry.getAddress();
  const crDeployTx = credentialRegistry.deploymentTransaction();
  const crReceipt = await crDeployTx?.wait();

  // Verify contract bytecode presence
  const crBytecode = await provider.getCode(credentialRegistryAddress);
  if (!crBytecode || crBytecode === "0x" || crBytecode.length <= 2) {
    throw new Error(`CredentialRegistry deployment failed: no contract bytecode found at ${credentialRegistryAddress}`);
  }
  console.log(`  -> CredentialRegistry deployed at: ${credentialRegistryAddress}`);
  console.log(`  -> Transaction Hash: ${crDeployTx?.hash}`);
  console.log(`  -> Block Number: ${crReceipt?.blockNumber}`);

  // 7. Record Non-Secret Deployment Manifest
  const deploymentsDir = path.resolve(__dirname, "../deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir, { recursive: true });
  }

  const timestamp = new Date().toISOString();
  const manifest = {
    network: network.name,
    chainId: actualChainId,
    deployer: deployer.address,
    timestamp: timestamp,
    blockNumber: crReceipt?.blockNumber ?? irReceipt?.blockNumber,
    preflight: {
      totalGas: preflight.totalGas.toString(),
      expectedCostEth: preflight.expectedCostEth,
      conservativeCostEth: preflight.conservativeCostEth,
      safetyMarginPercent: Number(preflight.safetyMarginPercent),
      feeOverrides: Object.fromEntries(
        Object.entries(preflight.feeOverrides).map(([k, v]) => [k, v?.toString()])
      ),
    },
    contracts: {
      IssuerRegistry: {
        contractName: "IssuerRegistry",
        address: issuerRegistryAddress,
        transactionHash: irDeployTx?.hash,
        blockNumber: irReceipt?.blockNumber,
        constructorArguments: [deployer.address],
      },
      CredentialRegistry: {
        contractName: "CredentialRegistry",
        address: credentialRegistryAddress,
        transactionHash: crDeployTx?.hash,
        blockNumber: crReceipt?.blockNumber,
        constructorArguments: [issuerRegistryAddress],
      },
    },
  };

  // Safe rerun manifest writing: write network-specific file and timestamped history
  const networkManifestPath = path.join(deploymentsDir, `${network.name}-${actualChainId}.json`);
  const timestampedManifestPath = path.join(
    deploymentsDir,
    `${network.name}-${actualChainId}-${Date.now()}.json`
  );
  const latestManifestPath = path.join(deploymentsDir, "latest.json");

  fs.writeFileSync(networkManifestPath, JSON.stringify(manifest, null, 2), "utf-8");
  fs.writeFileSync(timestampedManifestPath, JSON.stringify(manifest, null, 2), "utf-8");
  fs.writeFileSync(latestManifestPath, JSON.stringify(manifest, null, 2), "utf-8");
  console.log(`\nDeployment manifest successfully saved to:\n  - ${networkManifestPath}\n  - ${timestampedManifestPath}`);

  // 8. Output Configuration Instructions
  console.log("\n========================================================");
  console.log("DEPLOYMENT COMPLETE! Apply to backend/.env and docker-compose.yml:");
  console.log(`BLOCKCHAIN_RPC_URL=${process.env.BLOCKCHAIN_RPC_URL || "http://127.0.0.1:8545"}`);
  console.log(`BLOCKCHAIN_CHAIN_ID=${actualChainId}`);
  console.log(`ISSUER_REGISTRY_ADDRESS=${issuerRegistryAddress}`);
  console.log(`CREDENTIAL_REGISTRY_ADDRESS=${credentialRegistryAddress}`);
  console.log("========================================================\n");
}

main().catch((error) => {
  console.error("\n[DEPLOYMENT ERROR]:", error.message || error);
  process.exitCode = 1;
});
