from fastapi import FastAPI, APIRouter, HTTPException, Response, Request, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import secrets
from web3 import Web3
from web3.exceptions import ContractLogicError
import httpx

from price_service import get_price_service, DataQuality

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Admin password from env
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')
SESSION_SECRET = os.environ.get('SESSION_SECRET', secrets.token_hex(32))

# RPC URLs
BASE_RPC_URL = os.environ.get('BASE_RPC_URL', 'https://mainnet.base.org')
BASE_SEPOLIA_RPC_URL = os.environ.get('BASE_SEPOLIA_RPC_URL', 'https://sepolia.base.org')

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Session store (in production, use Redis)
active_sessions = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ====================
# Web3 Helpers
# ====================

def get_web3(chain_id: int) -> Web3:
    """Get Web3 instance for the given chain."""
    if chain_id == 8453:  # Base Mainnet
        return Web3(Web3.HTTPProvider(BASE_RPC_URL))
    elif chain_id == 84532:  # Base Sepolia
        return Web3(Web3.HTTPProvider(BASE_SEPOLIA_RPC_URL))
    else:
        raise ValueError(f"Unsupported chain ID: {chain_id}")

# ====================
# Contract ABIs
# ====================

VAULT_ABI = [
    {"type": "function", "name": "totalAssets", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "pricePerShare", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "totalSupply", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
]

STRATEGY_ABI = [
    {"type": "function", "name": "balanceOf", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "lastHarvest", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
]

ERC20_ABI = [
    {"type": "function", "name": "decimals", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint8"}]},
    {"type": "function", "name": "totalSupply", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "symbol", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "string"}]},
]

# Uniswap V2 Pair ABI
UNISWAP_V2_PAIR_ABI = [
    {"type": "function", "name": "getReserves", "stateMutability": "view",
     "inputs": [], "outputs": [
         {"name": "reserve0", "type": "uint112"},
         {"name": "reserve1", "type": "uint112"},
         {"name": "blockTimestampLast", "type": "uint32"}
     ]},
    {"type": "function", "name": "totalSupply", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "token0", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"type": "function", "name": "token1", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "address"}]},
    {"type": "function", "name": "decimals", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint8"}]},
]

# MasterChef-style Farm ABI
MASTERCHEF_ABI = [
    {"type": "function", "name": "rewardPerBlock", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "rewardPerSecond", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "totalAllocPoint", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
    {"type": "function", "name": "poolInfo", "stateMutability": "view",
     "inputs": [{"name": "pid", "type": "uint256"}],
     "outputs": [
         {"name": "lpToken", "type": "address"},
         {"name": "allocPoint", "type": "uint256"},
         {"name": "lastRewardBlock", "type": "uint256"},
         {"name": "accRewardPerShare", "type": "uint256"}
     ]},
    {"type": "function", "name": "poolLength", "stateMutability": "view",
     "inputs": [], "outputs": [{"type": "uint256"}]},
]

# ====================
# Price Cache
# ====================

# Token price cache: {address: (price_usd, timestamp)}
token_price_cache = {}
PRICE_CACHE_TTL = 300  # 5 minutes
PRICE_STALE_THRESHOLD = 600  # 10 minutes

# Known token addresses on Base (for CoinGecko mapping)
BASE_TOKEN_COINGECKO_IDS = {
    "0x4200000000000000000000000000000000000006": "weth",  # WETH on Base
    "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "usd-coin",  # USDC on Base
    "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": "dai",  # DAI on Base
    "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": "coinbase-wrapped-staked-eth",  # cbETH
}

# ====================
# Helper Functions
# ====================

def get_token_decimals(w3: Web3, token_address: str) -> int:
    """Read decimals from ERC20 token contract."""
    if not token_address or not w3.is_address(token_address):
        return 18
    try:
        contract = w3.eth.contract(
            address=w3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        return contract.functions.decimals().call()
    except Exception as e:
        logger.warning(f"Failed to read decimals for {token_address}: {e}")
        return 18

async def fetch_token_price_coingecko(token_address: str, chain_id: int) -> tuple[float, str]:
    """
    Fetch token price from CoinGecko API.
    Returns (price_usd, status) where status is 'ok', 'stale', or 'error'.
    """
    cache_key = f"{chain_id}:{token_address.lower()}"
    now = datetime.now(timezone.utc)
    
    # Check cache first
    if cache_key in token_price_cache:
        cached_price, cached_time = token_price_cache[cache_key]
        age_seconds = (now - cached_time).total_seconds()
        if age_seconds < PRICE_CACHE_TTL:
            return cached_price, "ok"
        elif age_seconds < PRICE_STALE_THRESHOLD:
            return cached_price, "stale"
    
    # For testnet, return mock prices
    if chain_id == 84532:
        mock_prices = {
            "weth": 3000.0,
            "usdc": 1.0,
            "dai": 1.0,
        }
        # Return mock based on address patterns
        token_price_cache[cache_key] = (100.0, now)
        return 100.0, "ok"
    
    # Look up CoinGecko ID
    coingecko_id = BASE_TOKEN_COINGECKO_IDS.get(token_address.lower())
    
    if not coingecko_id:
        # Unknown token - try to fetch by contract address
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # CoinGecko API for Base tokens by contract
                url = f"https://api.coingecko.com/api/v3/simple/token_price/base"
                params = {
                    "contract_addresses": token_address.lower(),
                    "vs_currencies": "usd"
                }
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    if token_address.lower() in data:
                        price = data[token_address.lower()].get("usd", 0)
                        if price > 0:
                            token_price_cache[cache_key] = (price, now)
                            return price, "ok"
        except Exception as e:
            logger.warning(f"CoinGecko contract lookup failed for {token_address}: {e}")
        
        # Return cached stale price if available
        if cache_key in token_price_cache:
            return token_price_cache[cache_key][0], "stale"
        return 0.0, "error"
    
    # Fetch by CoinGecko ID
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": coingecko_id,
                "vs_currencies": "usd"
            }
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                if coingecko_id in data:
                    price = data[coingecko_id].get("usd", 0)
                    if price > 0:
                        token_price_cache[cache_key] = (price, now)
                        return price, "ok"
    except Exception as e:
        logger.warning(f"CoinGecko price fetch failed for {coingecko_id}: {e}")
    
    # Return cached stale price if available
    if cache_key in token_price_cache:
        return token_price_cache[cache_key][0], "stale"
    return 0.0, "error"

async def get_lp_token_price(
    w3: Web3,
    lp_address: str,
    chain_id: int
) -> tuple[float, str]:
    """
    Calculate Uniswap V2-style LP token price.
    LP price = (reserve0 * price0 + reserve1 * price1) / totalSupply
    Returns (price_usd, data_quality).
    """
    if not lp_address or not w3.is_address(lp_address):
        return 0.0, "error"
    
    data_quality = "ok"
    
    try:
        lp_contract = w3.eth.contract(
            address=w3.to_checksum_address(lp_address),
            abi=UNISWAP_V2_PAIR_ABI
        )
        
        # Fetch LP data
        try:
            reserves = lp_contract.functions.getReserves().call()
            reserve0, reserve1, _ = reserves
        except Exception:
            # Not a Uniswap V2 LP - might be a single token
            # Fall back to direct price lookup
            price, status = await fetch_token_price_coingecko(lp_address, chain_id)
            return price, status
        
        total_supply = lp_contract.functions.totalSupply().call()
        token0_address = lp_contract.functions.token0().call()
        token1_address = lp_contract.functions.token1().call()
        
        if total_supply == 0:
            return 0.0, "error"
        
        # Get token decimals
        token0_decimals = get_token_decimals(w3, token0_address)
        token1_decimals = get_token_decimals(w3, token1_address)
        lp_decimals = get_token_decimals(w3, lp_address)
        
        # Normalize reserves
        reserve0_normalized = reserve0 / (10 ** token0_decimals)
        reserve1_normalized = reserve1 / (10 ** token1_decimals)
        total_supply_normalized = total_supply / (10 ** lp_decimals)
        
        # Fetch token prices
        price0, status0 = await fetch_token_price_coingecko(token0_address, chain_id)
        price1, status1 = await fetch_token_price_coingecko(token1_address, chain_id)
        
        # Update data quality
        if status0 == "error" or status1 == "error":
            data_quality = "error"
        elif status0 == "stale" or status1 == "stale":
            data_quality = "stale"
        
        if price0 == 0 and price1 == 0:
            return 0.0, "error"
        
        # Calculate LP price
        # LP price = (reserve0 * price0 + reserve1 * price1) / totalSupply
        total_value = (reserve0_normalized * price0) + (reserve1_normalized * price1)
        lp_price = total_value / total_supply_normalized if total_supply_normalized > 0 else 0
        
        return lp_price, data_quality
        
    except Exception as e:
        logger.error(f"Failed to calculate LP price for {lp_address}: {e}")
        return 0.0, "error"

async def get_farm_emissions(
    w3: Web3,
    farm_address: str,
    lp_address: str,
    reward_token_address: str,
    chain_id: int
) -> tuple[float, float, str]:
    """
    Fetch MasterChef-style farm emissions.
    Returns (yearly_rewards, reward_token_price_usd, data_quality).
    """
    if not farm_address or not w3.is_address(farm_address):
        return 0.0, 0.0, "error"
    
    data_quality = "ok"
    
    try:
        farm_contract = w3.eth.contract(
            address=w3.to_checksum_address(farm_address),
            abi=MASTERCHEF_ABI
        )
        
        # Try to get reward rate (different farms use different names)
        reward_per_second = 0
        reward_per_block = 0
        
        try:
            reward_per_second = farm_contract.functions.rewardPerSecond().call()
        except Exception:
            pass
        
        if reward_per_second == 0:
            try:
                reward_per_block = farm_contract.functions.rewardPerBlock().call()
            except Exception:
                pass
        
        if reward_per_second == 0 and reward_per_block == 0:
            logger.debug(f"No reward rate found for farm {farm_address}")
            return 0.0, 0.0, "error"
        
        # Get allocation points
        total_alloc_point = 1
        pool_alloc_point = 1
        
        try:
            total_alloc_point = farm_contract.functions.totalAllocPoint().call()
        except Exception:
            pass
        
        # Find the pool for our LP token
        try:
            pool_length = farm_contract.functions.poolLength().call()
            for pid in range(min(pool_length, 50)):  # Limit search
                try:
                    pool_info = farm_contract.functions.poolInfo(pid).call()
                    if pool_info[0].lower() == lp_address.lower():
                        pool_alloc_point = pool_info[1]
                        break
                except Exception:
                    continue
        except Exception:
            pass
        
        # Calculate pool's share of rewards
        pool_share = pool_alloc_point / total_alloc_point if total_alloc_point > 0 else 0
        
        # Get reward token decimals
        reward_decimals = get_token_decimals(w3, reward_token_address) if reward_token_address else 18
        
        # Calculate yearly rewards
        if reward_per_second > 0:
            seconds_per_year = 365 * 24 * 60 * 60
            yearly_rewards_raw = reward_per_second * seconds_per_year * pool_share
        else:
            # Assume ~2 second block time for Base
            blocks_per_year = (365 * 24 * 60 * 60) / 2
            yearly_rewards_raw = reward_per_block * blocks_per_year * pool_share
        
        yearly_rewards = yearly_rewards_raw / (10 ** reward_decimals)
        
        # Get reward token price
        reward_price, price_status = await fetch_token_price_coingecko(
            reward_token_address, chain_id
        ) if reward_token_address else (0.0, "error")
        
        if price_status != "ok":
            data_quality = price_status
        
        return yearly_rewards, reward_price, data_quality
        
    except Exception as e:
        logger.error(f"Failed to get farm emissions for {farm_address}: {e}")
        return 0.0, 0.0, "error"

def calculate_apy_from_apr(
    apr: float,
    compounds_per_day: int = 4,
    performance_fee: float = 0.045
) -> float:
    """
    Convert APR to APY with compounding and fees.
    
    Args:
        apr: Annual Percentage Rate (as decimal, e.g., 0.5 for 50%)
        compounds_per_day: Number of harvests per day
        performance_fee: Fee taken from rewards (e.g., 0.045 for 4.5%)
    
    Returns:
        APY as percentage (e.g., 50.0 for 50%)
    """
    if apr <= 0:
        return 0.0
    
    # Apply performance fee to APR
    apr_after_fee = apr * (1 - performance_fee)
    
    # Compounds per year
    n = compounds_per_day * 365
    
    # APY = (1 + APR/n)^n - 1
    # Using the compound interest formula
    try:
        apy = ((1 + apr_after_fee / n) ** n - 1) * 100
    except (OverflowError, ValueError):
        # If APR is too high, cap it
        apy = 10000.0
    
    # Cap at reasonable maximum
    return min(apy, 10000.0)

async def read_vault_on_chain(vault: dict) -> dict:
    """
    Read on-chain data from vault and strategy contracts.
    Returns dict with totalAssets, pricePerShare, lastHarvest, decimals, etc.
    """
    chain_id = vault.get('chainId', 84532)
    vault_address = vault.get('vaultAddress', '')
    strategy_address = vault.get('strategyAddress', '')
    want_address = vault.get('wantAddress', '')
    
    result = {
        'totalAssets': 0,
        'pricePerShare': 0,
        'totalSupply': 0,
        'lastHarvest': None,
        'strategyBalance': 0,
        'decimals': 18,
    }
    
    if not vault_address:
        return result
    
    try:
        w3 = get_web3(chain_id)
        
        # Get want token decimals
        result['decimals'] = get_token_decimals(w3, want_address)
        
        if not w3.is_address(vault_address):
            logger.warning(f"Invalid vault address: {vault_address}")
            return result
        
        vault_contract = w3.eth.contract(
            address=w3.to_checksum_address(vault_address),
            abi=VAULT_ABI
        )
        
        # Read vault data
        try:
            result['totalAssets'] = vault_contract.functions.totalAssets().call()
        except (ContractLogicError, Exception):
            logger.debug(f"totalAssets not available on vault {vault_address}")
        
        try:
            result['pricePerShare'] = vault_contract.functions.pricePerShare().call()
        except (ContractLogicError, Exception):
            logger.debug(f"pricePerShare not available on vault {vault_address}")
        
        try:
            result['totalSupply'] = vault_contract.functions.totalSupply().call()
        except (ContractLogicError, Exception):
            logger.debug(f"totalSupply not available on vault {vault_address}")
        
        # Read strategy data if address provided
        if strategy_address and w3.is_address(strategy_address):
            strategy_contract = w3.eth.contract(
                address=w3.to_checksum_address(strategy_address),
                abi=STRATEGY_ABI
            )
            
            try:
                result['strategyBalance'] = strategy_contract.functions.balanceOf().call()
            except (ContractLogicError, Exception):
                pass
            
            try:
                last_harvest_ts = strategy_contract.functions.lastHarvest().call()
                if last_harvest_ts > 0:
                    result['lastHarvest'] = datetime.fromtimestamp(last_harvest_ts, tz=timezone.utc).isoformat()
            except (ContractLogicError, Exception):
                pass
        
    except Exception as e:
        logger.error(f"Error reading vault on-chain data: {e}")
    
    return result

# ====================
# Models
# ====================

class Vault(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    chainId: int
    vaultAddress: str
    strategyAddress: str
    wantAddress: str  # LP token address
    token0: str
    token1: str
    rewardToken: str
    farmAddress: str
    routerAddress: str
    feeRecipients: List[str] = []
    paused: bool = False
    experimental: bool = False  # New: experimental vault flag
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class VaultCreate(BaseModel):
    name: str
    chainId: int
    vaultAddress: str
    strategyAddress: str
    wantAddress: str
    token0: str
    token1: str
    rewardToken: str
    farmAddress: str
    routerAddress: str
    feeRecipients: List[str] = []
    paused: bool = False
    experimental: bool = False

class VaultUpdate(BaseModel):
    name: Optional[str] = None
    chainId: Optional[int] = None
    vaultAddress: Optional[str] = None
    strategyAddress: Optional[str] = None
    wantAddress: Optional[str] = None
    token0: Optional[str] = None
    token1: Optional[str] = None
    rewardToken: Optional[str] = None
    farmAddress: Optional[str] = None
    routerAddress: Optional[str] = None
    feeRecipients: Optional[List[str]] = None
    paused: Optional[bool] = None
    experimental: Optional[bool] = None

class VaultMetrics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vaultId: str
    tvl: str = "0"  # Total Value Locked in USD
    apr: str = "0"  # Annual Percentage Rate
    apy: str = "0"  # Annual Percentage Yield (with compounding)
    pricePerShare: str = "1"
    totalSupply: str = "0"
    decimals: int = 18
    lpPrice: str = "0"  # LP token price in USD
    rewardPrice: str = "0"  # Reward token price in USD
    yearlyRewardsUsd: str = "0"  # Yearly rewards in USD
    dataQuality: str = "ok"  # "ok", "stale", or "error"
    lastHarvestAt: Optional[str] = None
    lastHarvestTx: Optional[str] = None
    updatedAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class HarvestEvent(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vaultId: str
    harvestAt: str
    txHash: str
    profit: str = "0"
    createdAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UserAction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    vaultId: str
    userAddress: str
    actionType: str  # "deposit" or "withdraw"
    amount: str
    txHash: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class UserActionCreate(BaseModel):
    vaultId: str
    userAddress: str
    actionType: str
    amount: str
    txHash: str

class AdminLogin(BaseModel):
    password: str

# ====================
# Auth Helpers
# ====================

def create_session():
    session_id = secrets.token_hex(32)
    active_sessions[session_id] = datetime.now(timezone.utc)
    return session_id

def verify_session(session_id: str) -> bool:
    if session_id in active_sessions:
        # Session expires after 24 hours
        created = active_sessions[session_id]
        if (datetime.now(timezone.utc) - created).total_seconds() < 86400:
            return True
        del active_sessions[session_id]
    return False

async def get_admin_session(request: Request):
    session_id = request.cookies.get("admin_session")
    if not session_id or not verify_session(session_id):
        raise HTTPException(status_code=401, detail="Unauthorized")
    return session_id

# ====================
# Auth Routes
# ====================

@api_router.post("/admin/login")
async def admin_login(data: AdminLogin, response: Response):
    if data.password == ADMIN_PASSWORD:
        session_id = create_session()
        response = JSONResponse(content={"success": True, "message": "Login successful"})
        response.set_cookie(
            key="admin_session",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=86400  # 24 hours
        )
        return response
    raise HTTPException(status_code=401, detail="Invalid password")

@api_router.post("/admin/logout")
async def admin_logout(response: Response, request: Request):
    session_id = request.cookies.get("admin_session")
    if session_id and session_id in active_sessions:
        del active_sessions[session_id]
    response = JSONResponse(content={"success": True, "message": "Logged out"})
    response.delete_cookie("admin_session")
    return response

@api_router.get("/admin/check")
async def check_admin_session(request: Request):
    session_id = request.cookies.get("admin_session")
    if session_id and verify_session(session_id):
        return {"authenticated": True}
    return {"authenticated": False}

# ====================
# Vault Routes
# ====================

@api_router.get("/vaults", response_model=List[Vault])
async def get_vaults():
    vaults = await db.vaults.find({}, {"_id": 0}).to_list(1000)
    return vaults

@api_router.get("/vaults/{vault_id}")
async def get_vault(vault_id: str):
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    return vault

@api_router.post("/vaults", response_model=Vault, status_code=201)
async def create_vault(data: VaultCreate, session: str = Depends(get_admin_session)):
    vault = Vault(**data.model_dump())
    doc = vault.model_dump()
    await db.vaults.insert_one(doc)
    
    # Create initial metrics
    metrics = VaultMetrics(vaultId=vault.id)
    await db.vault_metrics.insert_one(metrics.model_dump())
    
    return vault

@api_router.put("/vaults/{vault_id}", response_model=Vault)
async def update_vault(vault_id: str, data: VaultUpdate, session: str = Depends(get_admin_session)):
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}
    update_data["updatedAt"] = datetime.now(timezone.utc).isoformat()
    
    await db.vaults.update_one({"id": vault_id}, {"$set": update_data})
    updated = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    return updated

@api_router.delete("/vaults/{vault_id}")
async def delete_vault(vault_id: str, session: str = Depends(get_admin_session)):
    result = await db.vaults.delete_one({"id": vault_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    # Also delete metrics and events
    await db.vault_metrics.delete_many({"vaultId": vault_id})
    await db.harvest_events.delete_many({"vaultId": vault_id})
    
    return {"success": True, "message": "Vault deleted"}

# ====================
# Metrics Routes
# ====================

@api_router.get("/vaults/{vault_id}/metrics")
async def get_vault_metrics(vault_id: str):
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
    if not metrics:
        # Create default metrics if not exists
        metrics = VaultMetrics(vaultId=vault_id)
        await db.vault_metrics.insert_one(metrics.model_dump())
        metrics = metrics.model_dump()
    
    return metrics

@api_router.post("/vaults/{vault_id}/metrics/refresh")
async def refresh_vault_metrics(vault_id: str):
    """
    Refresh metrics from on-chain data.
    - Reads vault totalAssets and pricePerShare
    - Calculates LP price from Uniswap V2 reserves
    - Fetches farm emissions for APR
    - Converts APR to APY with compounding
    - Tracks data quality status
    """
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    chain_id = vault.get('chainId', 84532)
    want_address = vault.get('wantAddress', '')
    farm_address = vault.get('farmAddress', '')
    reward_token = vault.get('rewardToken', '')
    
    # Initialize data quality tracking
    data_quality = "ok"
    quality_issues = []
    
    try:
        w3 = get_web3(chain_id)
    except Exception as e:
        logger.error(f"Failed to connect to chain {chain_id}: {e}")
        return {"error": "Failed to connect to blockchain", "dataQuality": "error"}
    
    # Read on-chain vault data
    on_chain = await read_vault_on_chain(vault)
    decimals = on_chain['decimals']
    divisor = 10 ** decimals
    
    # Normalize vault values
    total_assets_normalized = on_chain['totalAssets'] / divisor if on_chain['totalAssets'] > 0 else 0
    price_per_share_normalized = on_chain['pricePerShare'] / divisor if on_chain['pricePerShare'] > 0 else 1.0
    
    # Calculate LP token price
    lp_price, lp_price_quality = await get_lp_token_price(w3, want_address, chain_id)
    
    if lp_price_quality == "error":
        quality_issues.append("lp_price_error")
        lp_price = 0.0
    elif lp_price_quality == "stale":
        quality_issues.append("lp_price_stale")
    
    # Calculate TVL
    tvl_usd = total_assets_normalized * lp_price
    
    # Get farm emissions and calculate APR/APY
    apr = 0.0
    apy = 0.0
    yearly_rewards_usd = 0.0
    reward_price = 0.0
    
    if farm_address and tvl_usd > 0:
        yearly_rewards, reward_price, farm_quality = await get_farm_emissions(
            w3, farm_address, want_address, reward_token, chain_id
        )
        
        if farm_quality == "error":
            quality_issues.append("farm_data_error")
        elif farm_quality == "stale":
            quality_issues.append("farm_data_stale")
        
        yearly_rewards_usd = yearly_rewards * reward_price
        
        # APR = (yearly_rewards_usd / TVL)
        if tvl_usd > 0:
            apr = yearly_rewards_usd / tvl_usd  # As decimal (e.g., 0.5 for 50%)
            
            # Convert APR to APY (4 compounds per day, 4.5% performance fee)
            apy = calculate_apy_from_apr(
                apr=apr,
                compounds_per_day=4,
                performance_fee=0.045
            )
    
    # Determine final data quality
    if "error" in str(quality_issues):
        data_quality = "error"
    elif quality_issues:
        data_quality = "stale"
    
    # Use on-chain lastHarvest if available
    last_harvest_at = on_chain.get('lastHarvest')
    
    update_data = {
        "tvl": str(round(tvl_usd, 2)),
        "apr": str(round(apr * 100, 2)),  # Store as percentage
        "apy": str(round(apy, 2)),
        "pricePerShare": str(round(price_per_share_normalized, 6)),
        "totalSupply": str(on_chain.get('totalSupply', 0)),
        "decimals": decimals,
        "lpPrice": str(round(lp_price, 6)),
        "rewardPrice": str(round(reward_price, 4)),
        "yearlyRewardsUsd": str(round(yearly_rewards_usd, 2)),
        "dataQuality": data_quality,
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    if last_harvest_at:
        update_data["lastHarvestAt"] = last_harvest_at
    
    await db.vault_metrics.update_one(
        {"vaultId": vault_id},
        {"$set": update_data},
        upsert=True
    )
    
    metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
    return metrics
    
    metrics = await db.vault_metrics.find_one({"vaultId": vault_id}, {"_id": 0})
    return metrics

# ====================
# Harvest Events Routes
# ====================

@api_router.get("/vaults/{vault_id}/harvests")
async def get_vault_harvests(vault_id: str, limit: int = 20):
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    harvests = await db.harvest_events.find(
        {"vaultId": vault_id},
        {"_id": 0}
    ).sort("harvestAt", -1).to_list(limit)
    
    return harvests

@api_router.post("/vaults/{vault_id}/harvests")
async def record_harvest(vault_id: str, txHash: str, profit: str = "0"):
    """Record a harvest event and update metrics"""
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    harvest = HarvestEvent(
        vaultId=vault_id,
        harvestAt=datetime.now(timezone.utc).isoformat(),
        txHash=txHash,
        profit=profit
    )
    await db.harvest_events.insert_one(harvest.model_dump())
    
    # Update metrics with last harvest info
    await db.vault_metrics.update_one(
        {"vaultId": vault_id},
        {
            "$set": {
                "lastHarvestAt": harvest.harvestAt,
                "lastHarvestTx": txHash,
                "updatedAt": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return harvest

# ====================
# User Actions Routes
# ====================

@api_router.post("/user-actions", response_model=UserAction)
async def record_user_action(data: UserActionCreate):
    action = UserAction(**data.model_dump())
    await db.user_actions.insert_one(action.model_dump())
    return action

@api_router.get("/user-actions/{user_address}")
async def get_user_actions(user_address: str, vault_id: Optional[str] = None, limit: int = 50):
    query = {"userAddress": user_address.lower()}
    if vault_id:
        query["vaultId"] = vault_id
    
    actions = await db.user_actions.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return actions

# ====================
# Root & Health
# ====================

@api_router.get("/")
async def root():
    return {"message": "BaseVault API", "version": "1.0.0"}

@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
