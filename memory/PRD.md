# BaseVault - DeFi Vault Dashboard PRD

## Original Problem Statement
Build a DeFi vault dashboard (Beefy-style) as a production-ready web app with:
- React + Tailwind + wagmi + viem + RainbowKit
- Base mainnet (8453) and Base Sepolia (84532) support with network switch UI
- Pages: /vaults, /vaults/[id], /admin/login, /admin/vaults
- Beefy-style APIs: /api/prices, /api/lps, /api/tvl, /api/apy
- Database: MongoDB with vaults, vault_metrics, harvest_events, user_actions tables

## User Choices
- Admin auth: Simple password protection with HttpOnly session cookie
- Design: Dark crypto/DeFi theme (Beefy Finance style)
- Additional: Harvest history, user action tracking
- API Style: Beefy-style dedicated endpoints with adapter pattern

## User Personas
1. **DeFi User**: Yield farmer looking to deposit LP tokens and earn auto-compounded returns
2. **Vault Admin**: Manager who configures and monitors vault settings

## Core Requirements
- [x] Wallet connection with RainbowKit
- [x] Network switching (Base Mainnet/Sepolia)
- [x] Vault listing with TVL, APY, status
- [x] Vault detail with metrics and contract addresses
- [x] Deposit/Withdraw UI (requires wallet connection)
- [x] Admin login with password protection
- [x] Admin CRUD for vault configurations
- [x] Harvest history tracking
- [x] User action recording
- [x] Beefy-style API endpoints (/prices, /lps, /tvl, /apy)
- [x] APY breakdown display (vaultApr, vaultApy, tradingApr, totalApy)
- [x] Data quality indicators (ok, stale, error)
- [x] Vault adapter pattern (UniswapV2, MasterChef)
- [x] Reusable pricing service with caching and rate limiting

## What's Been Implemented

### Backend (FastAPI + MongoDB)
- Vault CRUD APIs with admin session protection
- Vault metrics with refresh endpoint (on-chain data)
- Harvest events recording and listing
- User action tracking (deposit/withdraw)
- Session-based authentication
- **Beefy-style API endpoints**: `/api/prices`, `/api/lps`, `/api/tvl`, `/api/apy`, `/api/apy/{vault_id}`
- **Vault adapter pattern**: `vault_adapters.py` with LP adapters (UniswapV2, SingleToken) and Farm adapters (MasterChef, NoFarm)
- **Price service**: `price_service.py` with caching, rate-limiting, CoinGecko integration
- Admin price cache management endpoints

### Frontend (React + wagmi + RainbowKit)
- Dark DeFi theme with Manrope/Inter/JetBrains fonts
- Homepage with hero section
- Vaults list consuming Beefy-style `/api/tvl` and `/api/apy` endpoints
- Vault detail page with APY Breakdown card
- Data quality badges on vault cards and detail page
- Admin login and vault management panel
- Web3 integration (deposit/withdraw hooks)

## Database Schema
- `vaults`: id, name, chainId, addresses, tokens, paused, timestamps
- `vault_metrics`: vaultId, tvl, apy, pricePerShare, lastHarvest, dataQuality
- `harvest_events`: vaultId, harvestAt, txHash, profit
- `user_actions`: vaultId, userAddress, actionType, amount, txHash

## Architecture
```
/app/
├── backend/
│   ├── server.py           # Main FastAPI app, DB models, legacy routes
│   ├── beefy_api.py        # Beefy-style endpoints (/tvl, /apy, /prices, /lps)
│   ├── vault_adapters.py   # Adapter pattern for LP/Farm types
│   ├── price_service.py    # Reusable pricing with caching
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── lib/api.js      # API client (vaultApi, metricsApi, beefyApi, etc.)
│   │   ├── pages/          # VaultsPage, VaultDetailPage, Admin pages
│   │   ├── components/     # VaultCard, VaultActions, HarvestHistory, etc.
│   │   └── ...
│   └── .env
└── memory/PRD.md
```

## Prioritized Backlog

### P0 (Critical - Done)
- [x] Basic vault listing and detail pages
- [x] Admin authentication and vault CRUD
- [x] Dark theme UI implementation
- [x] Production-grade on-chain metrics (TVL, APY)
- [x] Reusable pricing service with caching
- [x] Beefy-style API endpoints
- [x] Frontend consuming Beefy-style APIs
- [x] APY breakdown display
- [x] Data quality indicators
- [x] Vault adapter pattern

### P1 (High Priority - Pending)
- [ ] Implement `tradingApr` calculation (currently placeholder 0)
- [ ] Add cron job for automatic metrics refresh
- [ ] Transaction confirmation toasts for deposit/withdraw

### P2 (Medium Priority)
- [ ] User portfolio page showing all deposits
- [ ] Harvest event listener/monitoring
- [ ] Error handling for failed transactions

### P3 (Nice to Have)
- [ ] Email notifications for harvests
- [ ] Multi-language support
- [ ] Dark/Light theme toggle

## Known Limitations
- `tradingApr` is a placeholder (hardcoded to 0) - needs DEX volume data
- On-chain calls for test vaults return 0 since underlying contracts are not deployed on testnet
- Testnet prices/LPs are mocked (100.0 and 200.0 respectively)
