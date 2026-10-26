import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";
import * as fs from "fs";
import * as path from "path";

// Helper to load non-secret and configured variables from .env if present
function loadEnv() {
  const candidates = [
    path.resolve(__dirname, "../.env"),
    path.resolve(__dirname, ".env"),
  ];
  for (const envPath of candidates) {
    if (fs.existsSync(envPath)) {
      try {
        const lines = fs.readFileSync(envPath, "utf-8").split("\n");
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
            const idx = trimmed.indexOf("=");
            const key = trimmed.slice(0, idx).trim();
            let val = trimmed.slice(idx + 1).trim();
            if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
              val = val.slice(1, -1);
            }
            if (!process.env[key] && val) {
              process.env[key] = val;
            }
          }
        }
      } catch (err) {
        // Fall back gracefully
      }
    }
  }
}
loadEnv();

function getAccounts(): string[] {
  const rawKey =
    process.env.BLOCKCHAIN_SIGNER_PRIVATE_KEY ||
    process.env.SEPOLIA_PRIVATE_KEY ||
    process.env.DEPLOYER_PRIVATE_KEY;
  if (!rawKey) return [];
  const clean = rawKey.trim();
  const formatted = clean.startsWith("0x") ? clean : "0x" + clean;
  if (formatted.length === 66) {
    return [formatted];
  }
  return [];
}

const config: HardhatUserConfig = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  networks: {
    hardhat: {
      chainId: 31337,
    },
    localhost: {
      url: process.env.BLOCKCHAIN_RPC_URL || "http://127.0.0.1:8545",
      chainId: 31337,
      accounts: getAccounts(),
    },
    sepolia: {
      url: process.env.BLOCKCHAIN_RPC_URL || process.env.SEPOLIA_RPC_URL || "",
      chainId: 11155111,
      accounts: getAccounts(),
      timeout: 60000,
    },
  },
  etherscan: {
    apiKey: process.env.ETHERSCAN_API_KEY || "",
  },
};

export default config;
