import { ethers } from "ethers";

export interface RawFeeData {
  gasPrice: bigint | null;
  maxFeePerGas: bigint | null;
  maxPriorityFeePerGas: bigint | null;
}

export interface FeeMetrics {
  baseFeePerGas: bigint | null;
  gasPrice: bigint | null;
  maxFeePerGas: bigint | null;
  maxPriorityFeePerGas: bigint | null;
  effectiveFeePerGas: bigint;
  feeType: "EIP-1559" | "Legacy";
  feeSourceDescription: string;
}

export interface DeploymentCostEstimate {
  totalGas: bigint;
  gasBreakdown: {
    issuerRegistryGas: bigint;
    credentialRegistryGas: bigint;
  };
  expectedCostWei: bigint;
  expectedCostEth: string;
  maxCostWei: bigint;
  maxCostEth: string;
  feeMetrics: FeeMetrics;
  isApproximate: true;
}

export interface BalanceEvaluation {
  isReady: boolean;
  status: "READY" | "BLOCKED_INSUFFICIENT_TEST_ETH" | "BLOCKED_FEE_DATA_UNAVAILABLE";
  message: string;
  balanceEth: string;
  requiredEth: string;
}

export interface DeploymentPreflightConfig {
  actualChainId: number;
  targetNetwork: string;
  allowMainnet?: boolean;
  safetyMarginPercent?: bigint;
}

export interface DeploymentPreflightReport {
  deployerAddress: string;
  balanceWei: bigint;
  balanceEth: string;
  totalGas: bigint;
  expectedCostWei: bigint;
  expectedCostEth: string;
  maxCostWei: bigint;
  maxCostEth: string;
  conservativeCostWei: bigint;
  conservativeCostEth: string;
  safetyMarginPercent: bigint;
  feeOverrides: {
    maxFeePerGas?: bigint;
    maxPriorityFeePerGas?: bigint;
    gasPrice?: bigint;
  };
  predictedIssuerRegistryAddress: string;
}

/**
 * Formats a fee amount in wei, providing both integer wei and gwei representations.
 * Handles sub-gwei values (e.g. 32 wei) without confusing decimal strings like '0.000000032 gwei'.
 */
export function formatFeeValue(feeWei: bigint | null | undefined): string {
  if (feeWei === null || feeWei === undefined) return "Unavailable";
  const gweiStr = ethers.formatUnits(feeWei, "gwei");
  if (feeWei < 1_000_000_000n) {
    return `${feeWei.toString()} wei (${gweiStr} gwei)`;
  }
  return `${gweiStr} gwei (${feeWei.toString()} wei)`;
}

/**
 * Extracts and distinguishes EIP-1559 and legacy fee metrics.
 * Ensures maxFeePerGas is never conflated with effective gasPrice.
 * Throws an Error if fee data is missing, null, or empty.
 */
export function parseFeeMetrics(
  feeData: RawFeeData | null | undefined,
  blockBaseFee?: bigint | null
): FeeMetrics {
  if (!feeData) {
    throw new Error("Fee data is null or undefined from provider.");
  }

  const { gasPrice, maxFeePerGas, maxPriorityFeePerGas } = feeData;
  const baseFee = blockBaseFee ?? null;

  // 1. EIP-1559 Fee Mode (Type 2)
  if (maxFeePerGas !== null && maxFeePerGas !== undefined) {
    let effective: bigint;
    let desc: string;

    if (baseFee !== null && maxPriorityFeePerGas !== null) {
      const calculated = baseFee + maxPriorityFeePerGas;
      effective = calculated < maxFeePerGas ? calculated : maxFeePerGas;
      desc = `Base fee (${baseFee.toString()} wei) + priority fee (${maxPriorityFeePerGas.toString()} wei)`;
    } else if (gasPrice !== null) {
      effective = gasPrice;
      desc = `Legacy gasPrice fallback (${gasPrice.toString()} wei)`;
    } else {
      effective = maxFeePerGas;
      desc = `Max fee per gas cap (${maxFeePerGas.toString()} wei)`;
    }

    return {
      baseFeePerGas: baseFee,
      gasPrice,
      maxFeePerGas,
      maxPriorityFeePerGas,
      effectiveFeePerGas: effective,
      feeType: "EIP-1559",
      feeSourceDescription: desc,
    };
  }

  // 2. Legacy Fee Mode (Type 0 / Type 1)
  if (gasPrice !== null && gasPrice !== undefined) {
    return {
      baseFeePerGas: null,
      gasPrice,
      maxFeePerGas: null,
      maxPriorityFeePerGas: null,
      effectiveFeePerGas: gasPrice,
      feeType: "Legacy",
      feeSourceDescription: `Legacy eth_gasPrice (${gasPrice.toString()} wei)`,
    };
  }

  throw new Error("Provider returned feeData with no valid gasPrice or maxFeePerGas.");
}

/**
 * Calculates estimated deployment cost using wei-safe BigInt arithmetic.
 * Never fabricates fallbacks; throws if gas or fee metrics are invalid.
 */
export function calculateDeploymentCost(
  irGas: bigint,
  crGas: bigint,
  feeMetrics: FeeMetrics
): DeploymentCostEstimate {
  if (irGas <= 0n || crGas <= 0n) {
    throw new Error("Gas units must be strictly positive BigInt values.");
  }

  const totalGas = irGas + crGas;
  const effectiveRate = feeMetrics.effectiveFeePerGas;
  const maxRate = feeMetrics.maxFeePerGas ?? effectiveRate;

  // Wei-safe BigInt arithmetic (strictly no JavaScript float loss of precision)
  const expectedCostWei = totalGas * effectiveRate;
  const maxCostWei = totalGas * maxRate;

  return {
    totalGas,
    gasBreakdown: {
      issuerRegistryGas: irGas,
      credentialRegistryGas: crGas,
    },
    expectedCostWei,
    expectedCostEth: ethers.formatEther(expectedCostWei),
    maxCostWei,
    maxCostEth: ethers.formatEther(maxCostWei),
    feeMetrics,
    isApproximate: true,
  };
}

/**
 * Calculates conservative deployment cost with a documented safety margin.
 * Default 25% buffer accounts for multi-block EIP-1559 base fee escalation (12.5% max per block).
 */
export function calculateConservativeCost(
  maxCostWei: bigint,
  safetyMarginPercent: bigint = 25n
): bigint {
  if (safetyMarginPercent < 0n) {
    throw new Error("Safety margin percent cannot be negative.");
  }
  return (maxCostWei * (100n + safetyMarginPercent)) / 100n;
}

/**
 * Constructs explicit validated fee overrides for transaction broadcasting.
 */
export function buildFeeOverrides(feeMetrics: FeeMetrics): {
  maxFeePerGas?: bigint;
  maxPriorityFeePerGas?: bigint;
  gasPrice?: bigint;
} {
  if (feeMetrics.feeType === "EIP-1559") {
    if (feeMetrics.maxFeePerGas === null || feeMetrics.maxPriorityFeePerGas === null) {
      throw new Error("EIP-1559 fee metrics must specify maxFeePerGas and maxPriorityFeePerGas.");
    }
    return {
      maxFeePerGas: feeMetrics.maxFeePerGas,
      maxPriorityFeePerGas: feeMetrics.maxPriorityFeePerGas,
    };
  }

  if (feeMetrics.gasPrice === null) {
    throw new Error("Legacy fee metrics must specify gasPrice.");
  }
  return { gasPrice: feeMetrics.gasPrice };
}

/**
 * Evaluates whether wallet balance is sufficient for deployment.
 * Never claims sufficient funds if cost estimate is unavailable.
 */
export function evaluateBalanceReadiness(
  balanceWei: bigint,
  estimate: DeploymentCostEstimate | null
): BalanceEvaluation {
  const balanceEth = ethers.formatEther(balanceWei);

  if (!estimate) {
    return {
      isReady: false,
      status: "BLOCKED_FEE_DATA_UNAVAILABLE",
      message: "Cost estimation is unavailable due to missing or invalid network fee data. Cannot verify balance sufficiency.",
      balanceEth,
      requiredEth: "Unknown",
    };
  }

  const requiredWei = estimate.maxCostWei;
  const requiredEth = estimate.maxCostEth;

  if (balanceWei === 0n) {
    return {
      isReady: false,
      status: "BLOCKED_INSUFFICIENT_TEST_ETH",
      message: `Deployer wallet has 0 ETH on Sepolia. Deployment requires approximately ${estimate.expectedCostEth} ETH (maximum fee cap: ${requiredEth} ETH).`,
      balanceEth,
      requiredEth,
    };
  }

  if (balanceWei < requiredWei) {
    return {
      isReady: false,
      status: "BLOCKED_INSUFFICIENT_TEST_ETH",
      message: `Deployer balance (${balanceEth} ETH) is less than the required maximum fee cap (${requiredEth} ETH).`,
      balanceEth,
      requiredEth,
    };
  }

  return {
    isReady: true,
    status: "READY",
    message: `Deployer wallet balance (${balanceEth} ETH) meets or exceeds the estimated deployment cost (expected: ~${estimate.expectedCostEth} ETH, cap: ${requiredEth} ETH).`,
    balanceEth,
    requiredEth,
  };
}

/**
 * Comprehensive pre-flight validation routine executed before ANY transaction is broadcast.
 * Strictly verifies chain ID, mainnet guard, gas estimates, fee data, and conservative balance requirements.
 */
export async function runPreflightValidation(
  provider: any,
  deployer: any,
  config: DeploymentPreflightConfig,
  issuerRegistryFactory: any,
  credentialRegistryFactory: any
): Promise<DeploymentPreflightReport> {
  // 1. Guard against ambiguous network selection
  if (!config.targetNetwork || config.targetNetwork === "default") {
    throw new Error(
      "Explicit network selection required. Run with '--network hardhat', '--network localhost', or '--network sepolia'."
    );
  }

  // 2. Mainnet guardrail
  if (config.actualChainId === 1 && !config.allowMainnet) {
    throw new Error(
      "CRITICAL SAFETY GUARD: Deployment to Ethereum Mainnet (Chain ID 1) is blocked. Explicit authorization required (ALLOW_MAINNET=true)."
    );
  }

  // 3. Network parity check
  if (config.targetNetwork === "sepolia" && config.actualChainId !== 11155111) {
    throw new Error(
      `Chain ID mismatch for network 'sepolia': expected 11155111, but connected to ${config.actualChainId}.`
    );
  }

  const deployerAddress = await deployer.getAddress();
  const currentNonce = await provider.getTransactionCount(deployerAddress);

  // Predict IssuerRegistry address using deterministic RLP create address formula
  const predictedIssuerRegistryAddress = ethers.getCreateAddress({
    from: deployerAddress,
    nonce: currentNonce,
  });

  // Query live fee data & block base fee without fallbacks
  const feeData = await provider.getFeeData();
  const latestBlock = await provider.getBlock("latest");
  const baseFee = latestBlock?.baseFeePerGas ?? null;

  const feeMetrics = parseFeeMetrics(feeData, baseFee);

  // Estimate gas using actual constructor arguments:
  // IssuerRegistry constructor(deployerAddress)
  const irDeployTx = await issuerRegistryFactory.getDeployTransaction(deployerAddress);
  const irGas = await provider.estimateGas(irDeployTx);

  // CredentialRegistry constructor(predictedIssuerRegistryAddress)
  const crDeployTx = await credentialRegistryFactory.getDeployTransaction(predictedIssuerRegistryAddress);
  const crGas = await provider.estimateGas(crDeployTx);

  if (irGas <= 0n || crGas <= 0n) {
    throw new Error("Gas estimation failed: reported gas units must be strictly positive.");
  }

  const costEstimate = calculateDeploymentCost(irGas, crGas, feeMetrics);

  // Calculate conservative cost using safety margin (default 25%)
  const safetyMargin = config.safetyMarginPercent ?? 25n;
  const conservativeCostWei = calculateConservativeCost(costEstimate.maxCostWei, safetyMargin);
  const conservativeCostEth = ethers.formatEther(conservativeCostWei);

  // Verify wallet balance covers the conservative maximum cost
  const balanceWei = await provider.getBalance(deployerAddress);
  const balanceEth = ethers.formatEther(balanceWei);

  if (balanceWei < conservativeCostWei) {
    throw new Error(
      `DEPLOYMENT BLOCKED: Insufficient balance for safe deployment. ` +
      `Deployer ${deployerAddress} has ${balanceEth} ETH, but conservative deployment cost ` +
      `with ${safetyMargin.toString()}% safety margin requires at least ${conservativeCostEth} ETH (${conservativeCostWei.toString()} wei). ` +
      `Zero transactions broadcasted.`
    );
  }

  const feeOverrides = buildFeeOverrides(feeMetrics);

  return {
    deployerAddress,
    balanceWei,
    balanceEth,
    totalGas: costEstimate.totalGas,
    expectedCostWei: costEstimate.expectedCostWei,
    expectedCostEth: costEstimate.expectedCostEth,
    maxCostWei: costEstimate.maxCostWei,
    maxCostEth: costEstimate.maxCostEth,
    conservativeCostWei,
    conservativeCostEth,
    safetyMarginPercent: safetyMargin,
    feeOverrides,
    predictedIssuerRegistryAddress,
  };
}
