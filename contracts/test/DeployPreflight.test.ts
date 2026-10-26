import { expect } from "chai";
import { ethers } from "hardhat";
import { runPreflightValidation } from "../scripts/fee-utils";

describe("Deployment Preflight & Zero-Transaction Guarantee", () => {
  let deployer: any;
  let IssuerRegistryFactory: any;
  let CredentialRegistryFactory: any;

  before(async () => {
    const signers = await ethers.getSigners();
    deployer = signers[0];
    IssuerRegistryFactory = await ethers.getContractFactory("IssuerRegistry");
    CredentialRegistryFactory = await ethers.getContractFactory("CredentialRegistry");
  });

  it("aborts safely and broadcasts zero transactions when wallet balance is 0", async () => {
    // Generate an unfunded random wallet
    const emptyWallet = ethers.Wallet.createRandom().connect(ethers.provider);
    const balance = await ethers.provider.getBalance(emptyWallet.address);
    expect(balance).to.equal(0n);

    const nonceBefore = await ethers.provider.getTransactionCount(emptyWallet.address);
    expect(nonceBefore).to.equal(0);

    let errorCaught: any = null;
    try {
      await runPreflightValidation(
        ethers.provider,
        emptyWallet,
        {
          actualChainId: 31337,
          targetNetwork: "hardhat",
          allowMainnet: false,
          safetyMarginPercent: 25n,
        },
        IssuerRegistryFactory,
        CredentialRegistryFactory
      );
    } catch (err: any) {
      errorCaught = err;
    }

    expect(errorCaught).to.not.be.null;
    expect(errorCaught.message).to.include("DEPLOYMENT BLOCKED: Insufficient balance for safe deployment");
    expect(errorCaught.message).to.include("Zero transactions broadcasted");

    // Cryptographic proof that zero transactions were broadcast
    const nonceAfter = await ethers.provider.getTransactionCount(emptyWallet.address);
    expect(nonceAfter).to.equal(0);
  });

  it("aborts safely and broadcasts zero transactions when balance is less than conservative cost", async () => {
    // Create wallet with minimal funds (50 wei), far below deployment cost
    const lowBalanceWallet = ethers.Wallet.createRandom().connect(ethers.provider);
    const fundTx = await deployer.sendTransaction({
      to: lowBalanceWallet.address,
      value: 50n,
    });
    await fundTx.wait();

    const initialBalance = await ethers.provider.getBalance(lowBalanceWallet.address);
    expect(initialBalance).to.equal(50n);

    const nonceBefore = await ethers.provider.getTransactionCount(lowBalanceWallet.address);
    expect(nonceBefore).to.equal(0);

    let errorCaught: any = null;
    try {
      await runPreflightValidation(
        ethers.provider,
        lowBalanceWallet,
        {
          actualChainId: 31337,
          targetNetwork: "hardhat",
          allowMainnet: false,
          safetyMarginPercent: 25n,
        },
        IssuerRegistryFactory,
        CredentialRegistryFactory
      );
    } catch (err: any) {
      errorCaught = err;
    }

    expect(errorCaught).to.not.be.null;
    expect(errorCaught.message).to.include("DEPLOYMENT BLOCKED: Insufficient balance for safe deployment");

    // Zero transactions broadcasted by lowBalanceWallet
    const nonceAfter = await ethers.provider.getTransactionCount(lowBalanceWallet.address);
    expect(nonceAfter).to.equal(0);
  });

  it("aborts safely and broadcasts zero transactions when fee data is missing or invalid", async () => {
    // Mock provider that returns null feeData
    const mockProvider = {
      ...ethers.provider,
      getFeeData: async () => null,
      getBlock: async () => ethers.provider.getBlock("latest"),
      getTransactionCount: (addr: string) => ethers.provider.getTransactionCount(addr),
      getBalance: (addr: string) => ethers.provider.getBalance(addr),
      estimateGas: (tx: any) => ethers.provider.estimateGas(tx),
    };

    const nonceBefore = await ethers.provider.getTransactionCount(deployer.address);

    let errorCaught: any = null;
    try {
      await runPreflightValidation(
        mockProvider,
        deployer,
        {
          actualChainId: 31337,
          targetNetwork: "hardhat",
          allowMainnet: false,
        },
        IssuerRegistryFactory,
        CredentialRegistryFactory
      );
    } catch (err: any) {
      errorCaught = err;
    }

    expect(errorCaught).to.not.be.null;
    expect(errorCaught.message).to.include("Fee data is null or undefined");

    const nonceAfter = await ethers.provider.getTransactionCount(deployer.address);
    expect(nonceAfter).to.equal(nonceBefore);
  });

  it("enforces the Ethereum Mainnet safeguard (Chain ID 1) with zero transactions", async () => {
    const nonceBefore = await ethers.provider.getTransactionCount(deployer.address);

    let errorCaught: any = null;
    try {
      await runPreflightValidation(
        ethers.provider,
        deployer,
        {
          actualChainId: 1, // Mainnet
          targetNetwork: "mainnet",
          allowMainnet: false,
        },
        IssuerRegistryFactory,
        CredentialRegistryFactory
      );
    } catch (err: any) {
      errorCaught = err;
    }

    expect(errorCaught).to.not.be.null;
    expect(errorCaught.message).to.include("CRITICAL SAFETY GUARD: Deployment to Ethereum Mainnet (Chain ID 1) is blocked");

    const nonceAfter = await ethers.provider.getTransactionCount(deployer.address);
    expect(nonceAfter).to.equal(nonceBefore);
  });

  it("enforces network parity for Sepolia with zero transactions", async () => {
    const nonceBefore = await ethers.provider.getTransactionCount(deployer.address);

    let errorCaught: any = null;
    try {
      await runPreflightValidation(
        ethers.provider,
        deployer,
        {
          actualChainId: 31337, // Local chain ID when targeting sepolia
          targetNetwork: "sepolia",
          allowMainnet: false,
        },
        IssuerRegistryFactory,
        CredentialRegistryFactory
      );
    } catch (err: any) {
      errorCaught = err;
    }

    expect(errorCaught).to.not.be.null;
    expect(errorCaught.message).to.include("Chain ID mismatch for network 'sepolia': expected 11155111, but connected to 31337");

    const nonceAfter = await ethers.provider.getTransactionCount(deployer.address);
    expect(nonceAfter).to.equal(nonceBefore);
  });

  it("succeeds and produces valid conservative cost and fee overrides for funded deployer", async () => {
    const nonceBefore = await ethers.provider.getTransactionCount(deployer.address);

    const report = await runPreflightValidation(
      ethers.provider,
      deployer,
      {
        actualChainId: 31337,
        targetNetwork: "hardhat",
        allowMainnet: false,
        safetyMarginPercent: 25n,
      },
      IssuerRegistryFactory,
      CredentialRegistryFactory
    );

    expect(report.deployerAddress).to.equal(deployer.address);
    expect(report.totalGas).to.be.greaterThan(0n);
    expect(report.expectedCostWei).to.be.greaterThan(0n);
    expect(report.maxCostWei).to.be.greaterThanOrEqual(report.expectedCostWei);

    // Verify 25% conservative safety margin math
    const expectedConservative = (report.maxCostWei * 125n) / 100n;
    expect(report.conservativeCostWei).to.equal(expectedConservative);

    // Verify predicted address formatting
    expect(ethers.isAddress(report.predictedIssuerRegistryAddress)).to.be.true;

    // Verify fee overrides are populated
    if (report.feeOverrides.maxFeePerGas) {
      expect(report.feeOverrides.maxFeePerGas).to.be.greaterThan(0n);
      expect(report.feeOverrides.maxPriorityFeePerGas).to.be.greaterThanOrEqual(0n);
    } else {
      expect(report.feeOverrides.gasPrice).to.be.greaterThan(0n);
    }

    // Verify that running preflight did NOT execute any transactions
    const nonceAfter = await ethers.provider.getTransactionCount(deployer.address);
    expect(nonceAfter).to.equal(nonceBefore);
  });
});
