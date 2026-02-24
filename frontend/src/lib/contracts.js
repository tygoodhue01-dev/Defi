// ERC20 ABI (minimal for balance, approve, allowance)
export const ERC20_ABI = [
  { type: "function", name: "approve", stateMutability: "nonpayable",
    inputs: [{ name: "spender", type: "address" }, { name: "amount", type: "uint256" }],
    outputs: [{ type: "bool" }] },
  { type: "function", name: "balanceOf", stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ type: "uint256" }] },
  { type: "function", name: "allowance", stateMutability: "view",
    inputs: [{ name: "owner", type: "address" }, { name: "spender", type: "address" }],
    outputs: [{ type: "uint256" }] },
  { type: "function", name: "decimals", stateMutability: "view", inputs: [], outputs: [{ type: "uint8" }] },
  { type: "function", name: "symbol", stateMutability: "view", inputs: [], outputs: [{ type: "string" }] },
  { type: "function", name: "name", stateMutability: "view", inputs: [], outputs: [{ type: "string" }] },
];

// Beefy-style Vault ABI (ERC4626-like)
export const VAULT_ABI = [
  // Read functions
  { type: "function", name: "balanceOf", stateMutability: "view",
    inputs: [{ name: "account", type: "address" }],
    outputs: [{ type: "uint256" }] },
  { type: "function", name: "totalSupply", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
  { type: "function", name: "balance", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
  { type: "function", name: "getPricePerFullShare", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
  { type: "function", name: "decimals", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint8" }] },
  { type: "function", name: "want", stateMutability: "view",
    inputs: [], outputs: [{ type: "address" }] },
  { type: "function", name: "strategy", stateMutability: "view",
    inputs: [], outputs: [{ type: "address" }] },
  // Write functions
  { type: "function", name: "deposit", stateMutability: "nonpayable",
    inputs: [{ name: "_amount", type: "uint256" }], outputs: [] },
  { type: "function", name: "depositAll", stateMutability: "nonpayable",
    inputs: [], outputs: [] },
  { type: "function", name: "withdraw", stateMutability: "nonpayable",
    inputs: [{ name: "_shares", type: "uint256" }], outputs: [] },
  { type: "function", name: "withdrawAll", stateMutability: "nonpayable",
    inputs: [], outputs: [] },
];

// Strategy ABI (for harvest info)
export const STRATEGY_ABI = [
  { type: "function", name: "harvest", stateMutability: "nonpayable",
    inputs: [], outputs: [] },
  { type: "function", name: "lastHarvest", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
  { type: "function", name: "balanceOf", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
];
