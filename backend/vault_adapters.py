"""
Vault Adapters - Adapter pattern for different vault types.

Supports:
- LP Types: UniswapV2, Solidly, Curve (extensible)
- Farm Types: MasterChef, Gauge, Staking (extensible)
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple
from web3 import Web3

logger = logging.getLogger(__name__)


class LPType(Enum):
    UNISWAP_V2 = "uniswap_v2"
    SOLIDLY = "solidly"
    CURVE = "curve"
    SINGLE_TOKEN = "single_token"


class FarmType(Enum):
    MASTERCHEF = "masterchef"
    MASTERCHEF_V2 = "masterchef_v2"
    GAUGE = "gauge"
    STAKING = "staking"
    NONE = "none"


@dataclass
class LPData:
    """Data from LP token contract."""
    total_supply: int
    reserve0: int
    reserve1: int
    token0: str
    token1: str
    token0_decimals: int
    token1_decimals: int
    lp_decimals: int


@dataclass
class FarmData:
    """Data from farm contract."""
    reward_per_second: float  # Normalized
    pool_share: float  # This pool's share of total rewards
    reward_token: str
    reward_decimals: int


@dataclass
class ApyBreakdown:
    """Beefy-style APY breakdown."""
    vault_apr: Optional[float] = None  # Base APR from farm, net of fee
    vault_apy: Optional[float] = None  # Compounded vault APR
    trading_apr: Optional[float] = None  # LP trading fees APR
    total_apy: Optional[float] = None  # Combined APY
    compoundings_per_year: int = 1460  # 4x per day
    beefy_performance_fee: float = 0.045  # 4.5%
    data_quality: str = "ok"


# ====================
# LP Adapters
# ====================

class LPAdapter(ABC):
    """Base class for LP token adapters."""
    
    @abstractmethod
    def get_lp_data(self, w3: Web3, lp_address: str) -> Optional[LPData]:
        """Fetch LP token data from chain."""
        pass
    
    @abstractmethod
    def calculate_lp_price(
        self,
        lp_data: LPData,
        token0_price: float,
        token1_price: float
    ) -> float:
        """Calculate LP token price from reserves and token prices."""
        pass


class UniswapV2LPAdapter(LPAdapter):
    """Adapter for Uniswap V2 style LP tokens."""
    
    ABI = [
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
    
    ERC20_ABI = [
        {"type": "function", "name": "decimals", "stateMutability": "view",
         "inputs": [], "outputs": [{"type": "uint8"}]},
    ]
    
    def get_lp_data(self, w3: Web3, lp_address: str) -> Optional[LPData]:
        if not lp_address or not w3.is_address(lp_address):
            return None
        
        try:
            lp_contract = w3.eth.contract(
                address=w3.to_checksum_address(lp_address),
                abi=self.ABI
            )
            
            # Get reserves
            reserves = lp_contract.functions.getReserves().call()
            reserve0, reserve1, _ = reserves
            
            # Get token addresses
            token0 = lp_contract.functions.token0().call()
            token1 = lp_contract.functions.token1().call()
            
            # Get total supply and decimals
            total_supply = lp_contract.functions.totalSupply().call()
            lp_decimals = lp_contract.functions.decimals().call()
            
            # Get token decimals
            token0_contract = w3.eth.contract(
                address=w3.to_checksum_address(token0),
                abi=self.ERC20_ABI
            )
            token1_contract = w3.eth.contract(
                address=w3.to_checksum_address(token1),
                abi=self.ERC20_ABI
            )
            
            token0_decimals = token0_contract.functions.decimals().call()
            token1_decimals = token1_contract.functions.decimals().call()
            
            return LPData(
                total_supply=total_supply,
                reserve0=reserve0,
                reserve1=reserve1,
                token0=token0,
                token1=token1,
                token0_decimals=token0_decimals,
                token1_decimals=token1_decimals,
                lp_decimals=lp_decimals
            )
            
        except Exception as e:
            logger.debug(f"Not a UniswapV2 LP or read failed for {lp_address}: {e}")
            return None
    
    def calculate_lp_price(
        self,
        lp_data: LPData,
        token0_price: float,
        token1_price: float
    ) -> float:
        if lp_data.total_supply == 0:
            return 0.0
        
        # Normalize reserves
        reserve0_norm = lp_data.reserve0 / (10 ** lp_data.token0_decimals)
        reserve1_norm = lp_data.reserve1 / (10 ** lp_data.token1_decimals)
        total_supply_norm = lp_data.total_supply / (10 ** lp_data.lp_decimals)
        
        # LP price = (reserve0 * price0 + reserve1 * price1) / totalSupply
        total_value = (reserve0_norm * token0_price) + (reserve1_norm * token1_price)
        return total_value / total_supply_norm if total_supply_norm > 0 else 0.0


class SingleTokenAdapter(LPAdapter):
    """Adapter for single token vaults (not LP)."""
    
    def get_lp_data(self, w3: Web3, lp_address: str) -> Optional[LPData]:
        # Single tokens don't have LP data
        return None
    
    def calculate_lp_price(
        self,
        lp_data: LPData,
        token0_price: float,
        token1_price: float
    ) -> float:
        # For single tokens, just return token0 price
        return token0_price


# ====================
# Farm Adapters
# ====================

class FarmAdapter(ABC):
    """Base class for farm adapters."""
    
    @abstractmethod
    def get_farm_data(
        self,
        w3: Web3,
        farm_address: str,
        lp_address: str,
        reward_token: str
    ) -> Optional[FarmData]:
        """Fetch farm data from chain."""
        pass
    
    def calculate_yearly_rewards(self, farm_data: FarmData) -> float:
        """Calculate yearly rewards in token units."""
        if not farm_data:
            return 0.0
        seconds_per_year = 365 * 24 * 60 * 60
        return farm_data.reward_per_second * seconds_per_year * farm_data.pool_share


class MasterChefAdapter(FarmAdapter):
    """Adapter for MasterChef-style farms."""
    
    ABI = [
        {"type": "function", "name": "rewardPerSecond", "stateMutability": "view",
         "inputs": [], "outputs": [{"type": "uint256"}]},
        {"type": "function", "name": "rewardPerBlock", "stateMutability": "view",
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
    
    ERC20_ABI = [
        {"type": "function", "name": "decimals", "stateMutability": "view",
         "inputs": [], "outputs": [{"type": "uint8"}]},
    ]
    
    def __init__(self, block_time: float = 2.0):
        """
        Args:
            block_time: Average block time in seconds (2s for Base)
        """
        self.block_time = block_time
    
    def get_farm_data(
        self,
        w3: Web3,
        farm_address: str,
        lp_address: str,
        reward_token: str
    ) -> Optional[FarmData]:
        if not farm_address or not w3.is_address(farm_address):
            return None
        
        try:
            farm_contract = w3.eth.contract(
                address=w3.to_checksum_address(farm_address),
                abi=self.ABI
            )
            
            # Try rewardPerSecond first, then rewardPerBlock
            reward_per_second = 0
            try:
                reward_per_second = farm_contract.functions.rewardPerSecond().call()
            except Exception:
                try:
                    reward_per_block = farm_contract.functions.rewardPerBlock().call()
                    reward_per_second = reward_per_block / self.block_time
                except Exception:
                    pass
            
            if reward_per_second == 0:
                return None
            
            # Get allocation points
            total_alloc = 1
            pool_alloc = 1
            
            try:
                total_alloc = farm_contract.functions.totalAllocPoint().call()
            except Exception:
                pass
            
            # Find pool for our LP
            try:
                pool_length = farm_contract.functions.poolLength().call()
                for pid in range(min(pool_length, 50)):
                    try:
                        pool_info = farm_contract.functions.poolInfo(pid).call()
                        if pool_info[0].lower() == lp_address.lower():
                            pool_alloc = pool_info[1]
                            break
                    except Exception:
                        continue
            except Exception:
                pass
            
            pool_share = pool_alloc / total_alloc if total_alloc > 0 else 0
            
            # Get reward token decimals
            reward_decimals = 18
            if reward_token and w3.is_address(reward_token):
                try:
                    token_contract = w3.eth.contract(
                        address=w3.to_checksum_address(reward_token),
                        abi=self.ERC20_ABI
                    )
                    reward_decimals = token_contract.functions.decimals().call()
                except Exception:
                    pass
            
            # Normalize reward per second
            reward_per_second_norm = reward_per_second / (10 ** reward_decimals)
            
            return FarmData(
                reward_per_second=reward_per_second_norm,
                pool_share=pool_share,
                reward_token=reward_token,
                reward_decimals=reward_decimals
            )
            
        except Exception as e:
            logger.error(f"Failed to get MasterChef data for {farm_address}: {e}")
            return None


class NoFarmAdapter(FarmAdapter):
    """Adapter for vaults without a farm (staking only)."""
    
    def get_farm_data(
        self,
        w3: Web3,
        farm_address: str,
        lp_address: str,
        reward_token: str
    ) -> Optional[FarmData]:
        return None


# ====================
# Adapter Registry
# ====================

class AdapterRegistry:
    """Registry for LP and Farm adapters."""
    
    def __init__(self):
        self._lp_adapters: Dict[LPType, LPAdapter] = {
            LPType.UNISWAP_V2: UniswapV2LPAdapter(),
            LPType.SINGLE_TOKEN: SingleTokenAdapter(),
        }
        self._farm_adapters: Dict[FarmType, FarmAdapter] = {
            FarmType.MASTERCHEF: MasterChefAdapter(),
            FarmType.MASTERCHEF_V2: MasterChefAdapter(),
            FarmType.NONE: NoFarmAdapter(),
        }
    
    def get_lp_adapter(self, lp_type: LPType) -> LPAdapter:
        return self._lp_adapters.get(lp_type, self._lp_adapters[LPType.UNISWAP_V2])
    
    def get_farm_adapter(self, farm_type: FarmType) -> FarmAdapter:
        return self._farm_adapters.get(farm_type, self._farm_adapters[FarmType.NONE])
    
    def register_lp_adapter(self, lp_type: LPType, adapter: LPAdapter):
        self._lp_adapters[lp_type] = adapter
    
    def register_farm_adapter(self, farm_type: FarmType, adapter: FarmAdapter):
        self._farm_adapters[farm_type] = adapter


# Global registry
_adapter_registry: Optional[AdapterRegistry] = None


def get_adapter_registry() -> AdapterRegistry:
    global _adapter_registry
    if _adapter_registry is None:
        _adapter_registry = AdapterRegistry()
    return _adapter_registry
