import { HardhatUserConfig } from 'hardhat/config';
import '@nomicfoundation/hardhat-toolbox';

// Deliberately does not read .env or configure any public network.
const config: HardhatUserConfig = {
  solidity: { version: '0.8.24', settings: { optimizer: { enabled: true, runs: 200 }, viaIR: true } },
  networks: { hardhat: { chainId: 31337 } },
};
export default config;
