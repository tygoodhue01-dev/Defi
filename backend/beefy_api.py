"""
Beefy-style API endpoints for vault metrics.

Endpoints:
- GET /api/prices - Token prices map
- GET /api/lps - LP prices map  
- GET /api/tvl - TVL per vault
- GET /api/apy - APY breakdown per vault
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from fastapi import APIRouter
from web3 import Web3
import os

from price_service import get_price_service, DataQuality
from vault_adapters import (
    get_adapter_registry,
    LPType, FarmType,
    ApyBreakdown
)

logger = logging.getLogger(__name__)

# Create router
beefy_router = APIRouter(prefix="/api")

# RPC URLs
BASE_RPC_URL = os.environ.get('BASE_RPC_URL', 'https://mainnet.base.org')
BASE_SEPOLIA_RPC_URL = os.environ.get('BASE_SEPOLIA_RPC_URL', 'https://sepolia.base.org')

# Default APY parameters
DEFAULT_COMPOUNDINGS_PER_YEAR = 1460  # 4x per day
DEFAULT_PERFORMANCE_FEE = 0.045  # 4.5%


def get_web3(chain_id: int) -> Web3:
    """Get Web3 instance for chain."""
    if chain_id == 8453:
        return Web3(Web3.HTTPProvider(BASE_RPC_URL))
    elif chain_id == 84532:
        return Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC_URL))
    raise ValueError(f"Unsupported chain: {chain_id}")


def calculate_vault_apy(
    vault_apr: float,
    compoundings_per_year: int = DEFAULT_COMPOUNDINGS_PER_YEAR,
    performance_fee: float = DEFAULT_PERFORMANCE_FEE
) -> float:
    """
    Calculate vault APY from APR with compounding.
    vaultApy = (1 + vaultApr / n)^n - 1
    where vaultApr is already net of performance fee
    """
    if vault_apr <= 0:
        return 0.0
    
    n = compoundings_per_year
    try:
        apy = ((1 + vault_apr / n) ** n) - 1
    except (OverflowError, ValueError):
        apy = 100.0  # Cap at 10000%
    
    return min(apy, 100.0)


def calculate_total_apy(vault_apy: float, trading_apr: float) -> float:
    """
    Calculate total APY combining vault APY and trading APR.
    totalApy = (1 + vaultApy) * (1 + tradingApr) - 1
    """
    return (1 + vault_apy) * (1 + trading_apr) - 1


async def compute_apy_breakdown(
    vault: Dict,
    tvl_usd: float,
    price_service,
    chain_id: int
) -> ApyBreakdown:
    """
    Compute full APY breakdown for a vault.
    """
    breakdown = ApyBreakdown(
        compoundings_per_year=DEFAULT_COMPOUNDINGS_PER_YEAR,
        beefy_performance_fee=DEFAULT_PERFORMANCE_FEE,
    )
    
    farm_address = vault.get('farmAddress', '')
    reward_token = vault.get('rewardToken', '')
    want_address = vault.get('wantAddress', '')
    
    # No farm = no APY from rewards
    if not farm_address or tvl_usd <= 0:
        breakdown.vault_apr = 0.0
        breakdown.vault_apy = 0.0
        breakdown.trading_apr = 0.0
        breakdown.total_apy = 0.0
        return breakdown
    
    try:
        w3 = get_web3(chain_id)
        
        # Get adapters
        registry = get_adapter_registry()
        lp_type = LPType(vault.get('lpType', 'uniswap_v2'))
        farm_type = FarmType(vault.get('farmType', 'masterchef'))
        
        farm_adapter = registry.get_farm_adapter(farm_type)
        
        # Get farm data
        farm_data = farm_adapter.get_farm_data(w3, farm_address, want_address, reward_token)
        
        if not farm_data:
            breakdown.data_quality = "error"
            return breakdown
        
        # Calculate yearly rewards
        yearly_rewards = farm_adapter.calculate_yearly_rewards(farm_data)
        
        # Get reward token price
        reward_price, price_quality = await price_service.get_token_price(reward_token, chain_id)
        
        if reward_price is None:
            breakdown.data_quality = "error"
            return breakdown
        
        if price_quality == DataQuality.STALE:
            breakdown.data_quality = "stale"
        elif price_quality == DataQuality.ERROR:
            breakdown.data_quality = "error"
            return breakdown
        
        # Calculate APR
        yearly_rewards_usd = yearly_rewards * reward_price
        gross_apr = yearly_rewards_usd / tvl_usd if tvl_usd > 0 else 0
        
        # Apply performance fee to get net APR
        breakdown.vault_apr = gross_apr * (1 - breakdown.beefy_performance_fee)
        
        # Calculate compounded APY
        breakdown.vault_apy = calculate_vault_apy(
            breakdown.vault_apr,
            breakdown.compoundings_per_year,
            0  # Fee already applied to APR
        )
        
        # Trading APR (0 for now - would need DEX volume data)
        breakdown.trading_apr = 0.0
        
        # Total APY
        breakdown.total_apy = calculate_total_apy(breakdown.vault_apy, breakdown.trading_apr)
        
        return breakdown
        
    except Exception as e:
        logger.error(f"Error computing APY for vault {vault.get('id')}: {e}")
        breakdown.data_quality = "error"
        return breakdown


# ====================
# MongoDB Access (injected)
# ====================

_db = None

def set_db(db):
    """Set database reference (called from server.py)."""
    global _db
    _db = db


def get_db():
    """Get database reference."""
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ====================
# Beefy-style Endpoints
# ====================

@beefy_router.get("/prices")
async def get_prices(chain_id: int = 8453):
    """
    Get all cached token prices (Beefy /prices style).
    Returns: {address: price_usd}
    """
    price_service = get_price_service()
    
    # If testnet, return mock data
    if chain_id == 84532:
        return {
            "0x0000000000000000000000000000000000000001": 100.0,
            "_meta": {"chain": chain_id, "source": "testnet_mock"}
        }
    
    prices = price_service.get_all_token_prices(chain_id)
    prices["_meta"] = {
        "chain": chain_id,
        "count": len(prices) - 1,
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    return prices


@beefy_router.get("/lps")
async def get_lps(chain_id: int = 8453):
    """
    Get all cached LP prices (Beefy /lps style).
    Returns: {address: price_usd}
    """
    price_service = get_price_service()
    
    if chain_id == 84532:
        return {
            "0x0000000000000000000000000000000000000001": 200.0,
            "_meta": {"chain": chain_id, "source": "testnet_mock"}
        }
    
    lps = price_service.get_all_lp_prices(chain_id)
    lps["_meta"] = {
        "chain": chain_id,
        "count": len(lps) - 1,
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    return lps


@beefy_router.get("/tvl")
async def get_tvl():
    """
    Get TVL for all vaults (Beefy /tvl style).
    Returns: {vault_id: tvl_usd}
    """
    db = get_db()
    price_service = get_price_service()
    
    vaults = await db.vaults.find({}, {"_id": 0}).to_list(1000)
    result = {}
    
    for vault in vaults:
        vault_id = vault.get('id')
        chain_id = vault.get('chainId', 84532)
        want_address = vault.get('wantAddress', '')
        
        # Get metrics from cache
        metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
        
        if metrics and metrics.get('tvl'):
            result[vault_id] = {
                "tvl": float(metrics.get('tvl', 0)),
                "chainId": chain_id,
                "dataQuality": metrics.get('dataQuality', 'ok')
            }
        else:
            # Calculate fresh TVL
            try:
                w3 = get_web3(chain_id)
                lp_price, quality = await price_service.get_lp_price(w3, want_address, chain_id)
                
                # Read total assets (simplified - would need vault contract read)
                tvl = 0.0
                result[vault_id] = {
                    "tvl": tvl,
                    "chainId": chain_id,
                    "dataQuality": quality.value if lp_price else "error"
                }
            except Exception as e:
                logger.error(f"Error calculating TVL for {vault_id}: {e}")
                result[vault_id] = {
                    "tvl": 0,
                    "chainId": chain_id,
                    "dataQuality": "error"
                }
    
    result["_meta"] = {
        "totalVaults": len(vaults),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    return result


@beefy_router.get("/apy")
async def get_apy():
    """
    Get APY breakdown for all vaults (Beefy /apy style).
    
    Returns per vault:
    - vaultApr: base APR from farm rewards (net of fee)
    - vaultApy: compounded vault APR
    - tradingApr: LP trading fees APR
    - totalApy: combined APY
    - compoundingsPerYear
    - beefyPerformanceFee
    - dataQuality
    """
    db = get_db()
    price_service = get_price_service()
    
    vaults = await db.vaults.find({}, {"_id": 0}).to_list(1000)
    result = {}
    
    for vault in vaults:
        vault_id = vault.get('id')
        chain_id = vault.get('chainId', 84532)
        
        # Get cached metrics
        metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
        tvl_usd = float(metrics.get('tvl', 0)) if metrics else 0
        
        # Compute APY breakdown
        breakdown = await compute_apy_breakdown(vault, tvl_usd, price_service, chain_id)
        
        # Format response
        if breakdown.data_quality == "error":
            result[vault_id] = {
                "vaultApr": None,
                "vaultApy": None,
                "tradingApr": None,
                "totalApy": None,
                "compoundingsPerYear": breakdown.compoundings_per_year,
                "beefyPerformanceFee": breakdown.beefy_performance_fee,
                "dataQuality": "error"
            }
        else:
            result[vault_id] = {
                "vaultApr": round(breakdown.vault_apr * 100, 4) if breakdown.vault_apr else 0,
                "vaultApy": round(breakdown.vault_apy * 100, 4) if breakdown.vault_apy else 0,
                "tradingApr": round(breakdown.trading_apr * 100, 4) if breakdown.trading_apr else 0,
                "totalApy": round(breakdown.total_apy * 100, 4) if breakdown.total_apy else 0,
                "compoundingsPerYear": breakdown.compoundings_per_year,
                "beefyPerformanceFee": breakdown.beefy_performance_fee,
                "dataQuality": breakdown.data_quality
            }
    
    result["_meta"] = {
        "totalVaults": len(vaults),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    return result


@beefy_router.get("/apy/{vault_id}")
async def get_vault_apy(vault_id: str):
    """
    Get APY breakdown for a specific vault.
    """
    db = get_db()
    price_service = get_price_service()
    
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        return {"error": "Vault not found", "dataQuality": "error"}
    
    chain_id = vault.get('chainId', 84532)
    
    # Get cached metrics
    metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
    tvl_usd = float(metrics.get('tvl', 0)) if metrics else 0
    
    # Compute APY breakdown
    breakdown = await compute_apy_breakdown(vault, tvl_usd, price_service, chain_id)
    
    if breakdown.data_quality == "error":
        return {
            "vaultId": vault_id,
            "vaultApr": None,
            "vaultApy": None,
            "tradingApr": None,
            "totalApy": None,
            "compoundingsPerYear": breakdown.compoundings_per_year,
            "beefyPerformanceFee": breakdown.beefy_performance_fee,
            "dataQuality": "error"
        }
    
    return {
        "vaultId": vault_id,
        "vaultApr": round(breakdown.vault_apr * 100, 4) if breakdown.vault_apr else 0,
        "vaultApy": round(breakdown.vault_apy * 100, 4) if breakdown.vault_apy else 0,
        "tradingApr": round(breakdown.trading_apr * 100, 4) if breakdown.trading_apr else 0,
        "totalApy": round(breakdown.total_apy * 100, 4) if breakdown.total_apy else 0,
        "compoundingsPerYear": breakdown.compoundings_per_year,
        "beefyPerformanceFee": breakdown.beefy_performance_fee,
        "dataQuality": breakdown.data_quality,
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
