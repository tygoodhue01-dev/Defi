import { http, createConfig, createStorage } from 'wagmi';
import { base, baseSepolia } from 'wagmi/chains';
import { getDefaultConfig } from '@rainbow-me/rainbowkit';

const projectId = process.env.REACT_APP_WALLETCONNECT_PROJECT_ID || 'demo_project_id';

// Create wagmi config with RainbowKit
export const config = getDefaultConfig({
  appName: 'BaseVault',
  projectId,
  chains: [base, baseSepolia],
  transports: {
    [base.id]: http(process.env.REACT_APP_BASE_RPC_URL || 'https://mainnet.base.org'),
    [baseSepolia.id]: http(process.env.REACT_APP_BASE_SEPOLIA_RPC_URL || 'https://sepolia.base.org'),
  },
});

// Export chains for use in components
export const supportedChains = [base, baseSepolia];

// Chain name mapping
export const chainNames = {
  [base.id]: 'Base Mainnet',
  [baseSepolia.id]: 'Base Sepolia',
};
