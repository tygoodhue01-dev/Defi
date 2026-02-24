# BaseVault - DeFi Vault Dashboard PRD

## Original Problem Statement
Build a DeFi vault dashboard (Beefy-style) as a production-ready web app with:
- React + Tailwind + wagmi + viem + RainbowKit
- Base mainnet (8453) and Base Sepolia (84532) support with network switch UI
- Pages: /vaults, /vaults/[id], /admin/login, /admin/vaults
- APIs: /api/vaults, /api/vaults/[id], /api/vaults/[id]/metrics
- Database: MongoDB with vaults, vault_metrics, harvest_events, user_actions tables

## User Choices
- Admin auth: Simple password protection with HttpOnly session cookie
- Design: Dark crypto/DeFi theme (Beefy Finance style)
- Additional: Harvest history, user action tracking

## User Personas
1. **DeFi User**: Yield farmer looking to deposit LP tokens and earn auto-compounded returns
2. **Vault Admin**: Manager who configures and monitors vault settings

## Core Requirements (Static)
- [x] Wallet connection with RainbowKit
- [x] Network switching (Base Mainnet/Sepolia)
- [x] Vault listing with TVL, APY, status
- [x] Vault detail with metrics and contract addresses
- [x] Deposit/Withdraw UI (requires wallet connection)
- [x] Admin login with password protection
- [x] Admin CRUD for vault configurations
- [x] Harvest history tracking
- [x] User action recording

## What's Been Implemented (Jan 25, 2026)
### Backend (FastAPI + MongoDB)
- Vault CRUD APIs with admin session protection
- Vault metrics with refresh endpoint (mock data)
- Harvest events recording and listing
- User action tracking (deposit/withdraw)
- Session-based authentication

### Frontend (React + wagmi + RainbowKit)
- Dark DeFi theme with Manrope/Inter/JetBrains fonts
- Homepage with hero section
- Vaults list with search, filters, stats
- Vault detail page with metrics, addresses, actions
- Admin login page
- Admin panel with vault management table
- Web3 integration ready (deposit/withdraw hooks)

## Database Schema
- `vaults`: id, name, chainId, addresses, tokens, paused, timestamps
- `vault_metrics`: vaultId, tvl, apy, pricePerShare, lastHarvest
- `harvest_events`: vaultId, harvestAt, txHash, profit
- `user_actions`: vaultId, userAddress, actionType, amount, txHash

## Prioritized Backlog

### P0 (Critical - Done)
- [x] Basic vault listing and detail pages
- [x] Admin authentication and vault CRUD
- [x] Dark theme UI implementation

### P1 (High Priority - Pending)
- [ ] Real blockchain data fetching (replace mock metrics)
- [ ] Transaction confirmation toasts
- [ ] Error handling for failed transactions

### P2 (Medium Priority)
- [ ] User portfolio page showing all deposits
- [ ] APY calculation from on-chain data
- [ ] Harvest event listener

### P3 (Nice to Have)
- [ ] Email notifications for harvests
- [ ] Multi-language support
- [ ] Dark/Light theme toggle

## Next Tasks
1. Add WalletConnect Project ID for production
2. Implement real blockchain data fetching for metrics
3. Add user portfolio view
4. Set up harvest event monitoring
