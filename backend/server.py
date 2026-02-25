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
import hashlib
from web3 import Web3
from web3.exceptions import ContractLogicError
import httpx

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

# Minimal ABIs for reading
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
]

# Simple LP price cache (in production, use Redis or proper cache)
lp_price_cache = {}

def get_token_decimals(w3: Web3, token_address: str) -> int:
    """Read decimals from ERC20 token contract."""
    if not token_address or not w3.is_address(token_address):
        return 18  # Default fallback
    try:
        contract = w3.eth.contract(
            address=w3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        return contract.functions.decimals().call()
    except Exception as e:
        logger.warning(f"Failed to read decimals for {token_address}: {e}")
        return 18  # Default fallback

async def get_lp_price_usd(lp_address: str, chain_id: int) -> float:
    """
    Get LP token price in USD.
    For MVP: returns a reasonable estimate.
    For production: integrate with DEX pricing or oracle.
    """
    cache_key = f"{chain_id}:{lp_address.lower()}"
    
    # Check cache (5 min TTL)
    if cache_key in lp_price_cache:
        cached_price, cached_time = lp_price_cache[cache_key]
        if (datetime.now(timezone.utc) - cached_time).total_seconds() < 300:
            return cached_price
    
    # For testnet, return mock price
    if chain_id == 84532:
        price = 100.0  # Mock $100 per LP on testnet
        lp_price_cache[cache_key] = (price, datetime.now(timezone.utc))
        return price
    
    # For mainnet, try to fetch from a pricing API
    # This is a simplified approach - production would use DEX pool math
    try:
        # Try CoinGecko or similar API for known tokens
        # For unknown LPs, estimate based on underlying tokens
        async with httpx.AsyncClient() as client:
            # This is a placeholder - in production, implement proper LP pricing
            # Options: 1) Query DEX pools, 2) Use LP token oracle, 3) Calculate from reserves
            pass
    except Exception as e:
        logger.warning(f"Failed to fetch LP price: {e}")
    
    # Default fallback price for unknown LPs
    price = 50.0
    lp_price_cache[cache_key] = (price, datetime.now(timezone.utc))
    return price

async def calculate_apy(
    tvl_usd: float,
    reward_token_price: float,
    daily_rewards: float,
    performance_fee: float = 0.045  # 4.5% default fee
) -> float:
    """
    Calculate APY from emission rate.
    APY = ((1 + daily_rate) ^ 365 - 1) * 100
    
    daily_rate = (daily_rewards * reward_price) / TVL
    """
    if tvl_usd <= 0:
        return 0.0
    
    daily_reward_usd = daily_rewards * reward_token_price
    daily_rate = daily_reward_usd / tvl_usd
    
    # Apply performance fee
    daily_rate_after_fee = daily_rate * (1 - performance_fee)
    
    # Compound daily for APY
    apy = ((1 + daily_rate_after_fee) ** 365 - 1) * 100
    
    # Cap at reasonable max
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
        
        # Validate addresses
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
        except ContractLogicError:
            logger.debug(f"totalAssets not available on vault {vault_address}")
        
        try:
            result['pricePerShare'] = vault_contract.functions.pricePerShare().call()
        except ContractLogicError:
            logger.debug(f"pricePerShare not available on vault {vault_address}")
        
        try:
            result['totalSupply'] = vault_contract.functions.totalSupply().call()
        except ContractLogicError:
            logger.debug(f"totalSupply not available on vault {vault_address}")
        
        # Read strategy data if address provided
        if strategy_address and w3.is_address(strategy_address):
            strategy_contract = w3.eth.contract(
                address=w3.to_checksum_address(strategy_address),
                abi=STRATEGY_ABI
            )
            
            try:
                result['strategyBalance'] = strategy_contract.functions.balanceOf().call()
            except ContractLogicError:
                pass
            
            try:
                last_harvest_ts = strategy_contract.functions.lastHarvest().call()
                if last_harvest_ts > 0:
                    result['lastHarvest'] = datetime.fromtimestamp(last_harvest_ts, tz=timezone.utc).isoformat()
            except ContractLogicError:
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
    apy: str = "0"  # Annual Percentage Yield
    pricePerShare: str = "1"
    totalSupply: str = "0"
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
    Reads vault contract, calculates TVL in USD, estimates APY.
    """
    vault = await db.vaults.find_one({"id": vault_id}, {"_id": 0})
    if not vault:
        raise HTTPException(status_code=404, detail="Vault not found")
    
    # Read on-chain data (includes decimals from want token)
    on_chain = await read_vault_on_chain(vault)
    decimals = on_chain['decimals']
    divisor = 10 ** decimals
    
    # Get LP price for TVL calculation
    lp_price = await get_lp_price_usd(
        vault.get('wantAddress', ''),
        vault.get('chainId', 84532)
    )
    
    # Normalize using want token decimals
    total_assets_normalized = on_chain['totalAssets'] / divisor if on_chain['totalAssets'] > 0 else 0
    tvl_usd = total_assets_normalized * lp_price
    
    # Normalize price per share using want token decimals
    price_per_share_normalized = on_chain['pricePerShare'] / divisor if on_chain['pricePerShare'] > 0 else 1.0
    
    # Estimate APY (simplified for MVP)
    estimated_daily_rewards = total_assets_normalized * 0.0001  # ~3.65% base APR assumption
    reward_token_price = 1.0  # Placeholder
    
    apy = await calculate_apy(
        tvl_usd=tvl_usd,
        reward_token_price=reward_token_price,
        daily_rewards=estimated_daily_rewards,
        performance_fee=0.045
    )
    
    # Use on-chain lastHarvest if available
    last_harvest_at = on_chain.get('lastHarvest')
    
    update_data = {
        "tvl": str(round(tvl_usd, 2)),
        "apy": str(round(apy, 2)),
        "pricePerShare": str(round(price_per_share_normalized, 6)),
        "totalSupply": str(on_chain.get('totalSupply', 0)),
        "decimals": decimals,
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
