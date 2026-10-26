import { expect } from "chai";
import { ethers } from "ethers";
import {
  formatFeeValue,
  parseFeeMetrics,
  calculateDeploymentCost,
  evaluateBalanceReadiness,
  FeeMetrics,
  DeploymentCostEstimate,
} from "../scripts/fee-utils";

describe("Fee Estimation & Gas Cost Utilities", () => {
  describe("formatFeeValue", () => {
    it("handles null and undefined gracefully", () => {
      expect(formatFeeValue(null)).to.equal("Unavailable");
      expect(formatFeeValue(undefined)).to.equal("Unavailable");
    });

    it("formats sub-gwei fees with explicit wei and gwei values", () => {
      // 32 wei: was previously reported confusingly as '0.000000032 gwei'
      const formatted = formatFeeValue(32n);
      expect(formatted).to.include("32 wei");
      expect(formatted).to.include("0.000000032 gwei");
    });

    it("formats typical gwei values clearly", () => {
      // 20 gwei = 20,000,000,000 wei
      const formatted = formatFeeValue(20_000_000_000n);
      expect(formatted).to.include("20.0 gwei");
      expect(formatted).to.include("20000000000 wei");
    });

    it("formats 1 wei boundary", () => {
      const formatted = formatFeeValue(1n);
      expect(formatted).to.include("1 wei");
      expect(formatted).to.include("0.000000001 gwei");
    });
  });

  describe("parseFeeMetrics", () => {
    it("correctly distinguishes EIP-1559 base fee, priority fee, and max fee cap", () => {
      const rawFee = {
        gasPrice: 17n,
        maxFeePerGas: 32n,
        maxPriorityFeePerGas: 2n,
      };
      const baseFee = 15n;

      const metrics = parseFeeMetrics(rawFee, baseFee);

      expect(metrics.feeType).to.equal("EIP-1559");
      expect(metrics.baseFeePerGas).to.equal(15n);
      expect(metrics.maxPriorityFeePerGas).to.equal(2n);
      expect(metrics.maxFeePerGas).to.equal(32n);
      expect(metrics.gasPrice).to.equal(17n);

      // Effective fee should be baseFee (15) + priorityFee (2) = 17 wei, NOT maxFeePerGas (32 wei)
      expect(metrics.effectiveFeePerGas).to.equal(17n);
      expect(metrics.feeSourceDescription).to.include("Base fee (15 wei) + priority fee (2 wei)");
    });

    it("caps effective fee at maxFeePerGas if base + priority exceeds cap", () => {
      const rawFee = {
        gasPrice: 50n,
        maxFeePerGas: 30n,
        maxPriorityFeePerGas: 10n,
      };
      const baseFee = 25n; // 25 + 10 = 35 > 30

      const metrics = parseFeeMetrics(rawFee, baseFee);
      expect(metrics.effectiveFeePerGas).to.equal(30n);
    });

    it("handles legacy network fee data when maxFeePerGas is null", () => {
      const rawFee = {
        gasPrice: 20_000_000_000n,
        maxFeePerGas: null,
        maxPriorityFeePerGas: null,
      };

      const metrics = parseFeeMetrics(rawFee, null);

      expect(metrics.feeType).to.equal("Legacy");
      expect(metrics.effectiveFeePerGas).to.equal(20_000_000_000n);
      expect(metrics.maxFeePerGas).to.be.null;
      expect(metrics.baseFeePerGas).to.be.null;
    });

    it("throws an error when fee data is null or empty", () => {
      expect(() => parseFeeMetrics(null)).to.throw("Fee data is null or undefined");
      expect(() => parseFeeMetrics(undefined)).to.throw("Fee data is null or undefined");
      expect(() =>
        parseFeeMetrics({ gasPrice: null, maxFeePerGas: null, maxPriorityFeePerGas: null })
      ).to.throw("no valid gasPrice or maxFeePerGas");
    });
  });

  describe("calculateDeploymentCost", () => {
    const feeMetrics: FeeMetrics = {
      baseFeePerGas: 15n,
      gasPrice: 17n,
      maxFeePerGas: 32n,
      maxPriorityFeePerGas: 2n,
      effectiveFeePerGas: 17n,
      feeType: "EIP-1559",
      feeSourceDescription: "Test EIP-1559",
    };

    it("calculates expected and maximum costs using wei-safe BigInt arithmetic", () => {
      const irGas = 887_906n;
      const crGas = 1_515_310n;
      const totalGas = irGas + crGas; // 2,403,216n

      const cost = calculateDeploymentCost(irGas, crGas, feeMetrics);

      expect(cost.totalGas).to.equal(2_403_216n);
      expect(cost.isApproximate).to.be.true;

      // Wei-safe arithmetic: 2,403,216 * 17n = 40,854,672n wei
      const expectedWei = totalGas * 17n;
      expect(cost.expectedCostWei).to.equal(expectedWei);
      expect(cost.expectedCostEth).to.equal(ethers.formatEther(expectedWei));

      // Max cost cap: 2,403,216 * 32n = 76,902,912n wei
      const maxWei = totalGas * 32n;
      expect(cost.maxCostWei).to.equal(maxWei);
      expect(cost.maxCostEth).to.equal(ethers.formatEther(maxWei));
    });

    it("preserves exact precision for large gas and fee numbers without float overflow", () => {
      const largeGas = 10_000_000n;
      const largeMetrics: FeeMetrics = {
        baseFeePerGas: 100_000_000_000n, // 100 gwei
        gasPrice: null,
        maxFeePerGas: 150_000_000_000n, // 150 gwei
        maxPriorityFeePerGas: 2_000_000_000n,
        effectiveFeePerGas: 102_000_000_000n, // 102 gwei
        feeType: "EIP-1559",
        feeSourceDescription: "High congestion test",
      };

      const cost = calculateDeploymentCost(5_000_000n, 5_000_000n, largeMetrics);
      expect(cost.expectedCostWei).to.equal(1_020_000_000_000_000_000n); // 1.02 ETH
      expect(cost.expectedCostEth).to.equal("1.02");
      expect(cost.maxCostWei).to.equal(1_500_000_000_000_000_000n); // 1.50 ETH
      expect(cost.maxCostEth).to.equal("1.5");
    });

    it("reverts if gas units are non-positive", () => {
      expect(() => calculateDeploymentCost(0n, 100n, feeMetrics)).to.throw(
        "Gas units must be strictly positive"
      );
      expect(() => calculateDeploymentCost(100n, 0n, feeMetrics)).to.throw(
        "Gas units must be strictly positive"
      );
    });
  });

  describe("evaluateBalanceReadiness", () => {
    const mockEstimate: DeploymentCostEstimate = {
      totalGas: 2_403_216n,
      gasBreakdown: { issuerRegistryGas: 887_906n, credentialRegistryGas: 1_515_310n },
      expectedCostWei: 40_854_672n,
      expectedCostEth: "0.000000040854672",
      maxCostWei: 76_902_912n,
      maxCostEth: "0.000000076902912",
      feeMetrics: {
        baseFeePerGas: 15n,
        gasPrice: 17n,
        maxFeePerGas: 32n,
        maxPriorityFeePerGas: 2n,
        effectiveFeePerGas: 17n,
        feeType: "EIP-1559",
        feeSourceDescription: "Test",
      },
      isApproximate: true,
    };

    it("marks readiness as UNAVAILABLE when estimate is null and never fabricates fallback", () => {
      const result = evaluateBalanceReadiness(ethers.parseEther("1.0"), null);
      expect(result.isReady).to.be.false;
      expect(result.status).to.equal("BLOCKED_FEE_DATA_UNAVAILABLE");
      expect(result.message).to.include("Cost estimation is unavailable");
      expect(result.requiredEth).to.equal("Unknown");
    });

    it("reports BLOCKED_INSUFFICIENT_TEST_ETH when wallet balance is 0", () => {
      const result = evaluateBalanceReadiness(0n, mockEstimate);
      expect(result.isReady).to.be.false;
      expect(result.status).to.equal("BLOCKED_INSUFFICIENT_TEST_ETH");
      expect(result.message).to.include("wallet has 0 ETH");
    });

    it("reports BLOCKED_INSUFFICIENT_TEST_ETH when balance is less than max cost cap", () => {
      // 50 wei balance, required max cap is 76_902_912 wei
      const result = evaluateBalanceReadiness(50n, mockEstimate);
      expect(result.isReady).to.be.false;
      expect(result.status).to.equal("BLOCKED_INSUFFICIENT_TEST_ETH");
      expect(result.message).to.include("is less than the required maximum fee cap");
    });

    it("reports READY when wallet balance meets or exceeds max cost cap", () => {
      // 0.05 ETH is well above 76_902_912 wei
      const balance = ethers.parseEther("0.05");
      const result = evaluateBalanceReadiness(balance, mockEstimate);
      expect(result.isReady).to.be.true;
      expect(result.status).to.equal("READY");
      expect(result.message).to.include("meets or exceeds");
    });
  });
});
