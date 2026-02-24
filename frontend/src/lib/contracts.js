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

// ERC4626-style Vault ABI
export const VAULT_ABI = [
  { type: "function", name: "deposit", stateMutability: "nonpayable",
    inputs: [{ name: "amount", type: "uint256" }], outputs: [] },
  { type: "function", name: "withdraw", stateMutability: "nonpayable",
    inputs: [{ name: "shares", type: "uint256" }], outputs: [] },
  { type: "function", name: "balanceOf", stateMutability: "view",
    inputs: [{ name: "user", type: "address" }], outputs: [{ type: "uint256" }] },
  { type: "function", name: "totalAssets", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
  { type: "function", name: "pricePerShare", stateMutability: "view",
    inputs: [], outputs: [{ type: "uint256" }] },
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
