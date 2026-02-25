"""
Price Service - Reusable pricing module with caching and rate limiting.

Features:
- Token price fetching from CoinGecko
- Uniswap V2 LP token pricing
- In-memory cache with TTL
- Rate limiting for API calls
- Data quality tracking
- Beefy-style batch price endpoints
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import httpx
from web3 import Web3

logger = logging.getLogger(__name__)


class DataQuality(Enum):
    OK = "ok"
    STALE = "stale"
    ERROR = "error"


@dataclass
class CacheEntry:
    value: Any
    timestamp: datetime
    quality: DataQuality = DataQuality.OK


@dataclass
class RateLimiter:
    """Simple rate limiter using token bucket algorithm."""
    max_tokens: int = 10
    refill_rate: float = 1.0  # tokens per second
    tokens: float = field(default=10.0)
    last_refill: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    async def acquire(self) -> bool:
        """Acquire a token, waiting if necessary. Returns True if acquired."""
        now = datetime.now(timezone.utc)
        elapsed = (now - self.last_refill).total_seconds()
        
        # Refill tokens
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        
        # Wait for next token
        wait_time = (1 - self.tokens) / self.refill_rate
        if wait_time <= 5:  # Max wait 5 seconds
            await asyncio.sleep(wait_time)
            self.tokens = 0
            return True
        
        return False


class PriceService:
    """
    Centralized price service with caching and rate limiting.
    
    Supports Beefy-style batch endpoints for prices and LP prices.
    """
    
    # Cache TTL settings (in seconds)
    CACHE_TTL = 300  # 5 minutes
    STALE_THRESHOLD = 600  # 10 minutes
    
    # Known token mappings for Base chain
    BASE_MAINNET_TOKENS = {
        "0x4200000000000000000000000000000000000006": "weth",
        "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913": "usd-coin",
        "0x50c5725949a6f0c72e6c4a641f24049a917db0cb": "dai",
        "0x2ae3f1ec7f1f5012cfeab0185bfc7aa3cf0dec22": "coinbase-wrapped-staked-eth",
        "0xd9aaec86b65d86f6a7b5b1b0c42ffa531710b6ca": "bridged-usd-coin-base",
    }
    
    # Testnet mock prices - ONLY used on testnet (chain 84532)
    TESTNET_MOCK_PRICES = {
        "weth": 3000.0,
        "usdc": 1.0,
        "dai": 1.0,
        "default_token": 100.0,
        "default_lp": 200.0,
    }
    
    # ABIs
    ERC20_ABI = [
        {"type": "function", "name": "decimals", "stateMutability": "view",
         "inputs": [], "outputs": [{"type": "uint8"}]},
        {"type": "function", "name": "symbol", "stateMutability": "view",
         "inputs": [], "outputs": [{"type": "string"}]},
    ]
    
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
    
    def __init__(self):
        self._token_cache: Dict[str, CacheEntry] = {}
        self._lp_cache: Dict[str, CacheEntry] = {}
        self._decimals_cache: Dict[str, int] = {}
        self._rate_limiter = RateLimiter(max_tokens=10, refill_rate=1.0)
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=10.0)
        return self._http_client
    
    async def close(self):
        """Close HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def _cache_key(self, chain_id: int, address: str) -> str:
        """Generate cache key."""
        return f"{chain_id}:{address.lower()}"
    
    def _get_cached_token(self, key: str) -> Optional[Tuple[float, DataQuality]]:
        """Get cached token price with quality status."""
        if key not in self._token_cache:
            return None
        
        entry = self._token_cache[key]
        age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
        
        if age < self.CACHE_TTL:
            return entry.value, DataQuality.OK
        elif age < self.STALE_THRESHOLD:
            return entry.value, DataQuality.STALE
        
        return None
    
    def _get_cached_lp(self, key: str) -> Optional[Tuple[float, DataQuality]]:
        """Get cached LP price with quality status."""
        if key not in self._lp_cache:
            return None
        
        entry = self._lp_cache[key]
        age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
        
        if age < self.CACHE_TTL:
            return entry.value, DataQuality.OK
        elif age < self.STALE_THRESHOLD:
            return entry.value, DataQuality.STALE
        
        return None
    
    def _set_cached_token(self, key: str, value: float, quality: DataQuality = DataQuality.OK):
        """Set token price cache entry."""
        self._token_cache[key] = CacheEntry(
            value=value,
            timestamp=datetime.now(timezone.utc),
            quality=quality
        )
    
    def _set_cached_lp(self, key: str, value: float, quality: DataQuality = DataQuality.OK):
        """Set LP price cache entry."""
        self._lp_cache[key] = CacheEntry(
            value=value,
            timestamp=datetime.now(timezone.utc),
            quality=quality
        )
    
    def get_token_decimals(self, w3: Web3, token_address: str) -> int:
        """Read decimals from ERC20 token contract (cached)."""
        if not token_address or not w3.is_address(token_address):
            return 18
        
        addr_lower = token_address.lower()
        if addr_lower in self._decimals_cache:
            return self._decimals_cache[addr_lower]
        
        try:
            contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            decimals = contract.functions.decimals().call()
            self._decimals_cache[addr_lower] = decimals
            return decimals
        except Exception as e:
            logger.warning(f"Failed to read decimals for {token_address}: {e}")
            return 18
    
    def is_testnet(self, chain_id: int) -> bool:
        """Check if chain is testnet."""
        return chain_id == 84532
    
    async def get_token_price(
        self,
        token_address: str,
        chain_id: int
    ) -> Tuple[Optional[float], DataQuality]:
        """
        Get token price in USD from CoinGecko.
        
        Returns:
            Tuple of (price_usd or None, data_quality)
            Returns None for price if data unavailable (not a guess)
        """
        if not token_address:
            return None, DataQuality.ERROR
        
        cache_key = self._cache_key(chain_id, token_address)
        
        # Check cache
        cached = self._get_cached_token(cache_key)
        if cached:
            return cached
        
        # Testnet: return mock prices
        if self.is_testnet(chain_id):
            price = self.TESTNET_MOCK_PRICES.get("default_token", 100.0)
            self._set_cached_token(cache_key, price)
            return price, DataQuality.OK
        
        # Production: fetch real prices
        # Rate limit check
        if not await self._rate_limiter.acquire():
            if cache_key in self._token_cache:
                return self._token_cache[cache_key].value, DataQuality.STALE
            return None, DataQuality.ERROR
        
        # Try CoinGecko by ID first
        coingecko_id = self.BASE_MAINNET_TOKENS.get(token_address.lower())
        
        try:
            client = await self._get_client()
            
            if coingecko_id:
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": coingecko_id, "vs_currencies": "usd"}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if coingecko_id in data and "usd" in data[coingecko_id]:
                        price = data[coingecko_id]["usd"]
                        self._set_cached_token(cache_key, price)
                        return price, DataQuality.OK
            
            # Try by contract address
            url = "https://api.coingecko.com/api/v3/simple/token_price/base"
            params = {"contract_addresses": token_address.lower(), "vs_currencies": "usd"}
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                addr_lower = token_address.lower()
                if addr_lower in data and "usd" in data[addr_lower]:
                    price = data[addr_lower]["usd"]
                    self._set_cached_token(cache_key, price)
                    return price, DataQuality.OK
            
            if response.status_code == 429:
                logger.warning("CoinGecko rate limit hit")
                if cache_key in self._token_cache:
                    return self._token_cache[cache_key].value, DataQuality.STALE
                    
        except Exception as e:
            logger.error(f"CoinGecko API error for {token_address}: {e}")
        
        # Return stale cache or None (not a guess)
        if cache_key in self._token_cache:
            return self._token_cache[cache_key].value, DataQuality.STALE
        
        return None, DataQuality.ERROR
    
    async def get_lp_price(
        self,
        w3: Web3,
        lp_address: str,
        chain_id: int
    ) -> Tuple[Optional[float], DataQuality]:
        """
        Calculate Uniswap V2-style LP token price.
        
        Returns:
            Tuple of (price_usd or None, data_quality)
            Returns None if calculation fails (not a guess)
        """
        if not lp_address or not w3.is_address(lp_address):
            return None, DataQuality.ERROR
        
        cache_key = self._cache_key(chain_id, lp_address)
        
        # Check cache
        cached = self._get_cached_lp(cache_key)
        if cached:
            return cached
        
        # Testnet: return mock price
        if self.is_testnet(chain_id):
            price = self.TESTNET_MOCK_PRICES.get("default_lp", 200.0)
            self._set_cached_lp(cache_key, price)
            return price, DataQuality.OK
        
        # Production: calculate from reserves
        quality = DataQuality.OK
        
        try:
            lp_contract = w3.eth.contract(
                address=w3.to_checksum_address(lp_address),
                abi=self.UNISWAP_V2_PAIR_ABI
            )
            
            # Try to get reserves
            try:
                reserves = lp_contract.functions.getReserves().call()
                reserve0, reserve1, _ = reserves
            except Exception:
                # Not a Uniswap V2 LP - try direct price lookup
                return await self.get_token_price(lp_address, chain_id)
            
            # Get LP data
            total_supply = lp_contract.functions.totalSupply().call()
            if total_supply == 0:
                return None, DataQuality.ERROR
            
            token0_address = lp_contract.functions.token0().call()
            token1_address = lp_contract.functions.token1().call()
            
            # Get decimals
            token0_decimals = self.get_token_decimals(w3, token0_address)
            token1_decimals = self.get_token_decimals(w3, token1_address)
            lp_decimals = self.get_token_decimals(w3, lp_address)
            
            # Normalize reserves
            reserve0_norm = reserve0 / (10 ** token0_decimals)
            reserve1_norm = reserve1 / (10 ** token1_decimals)
            total_supply_norm = total_supply / (10 ** lp_decimals)
            
            # Get token prices
            price0, quality0 = await self.get_token_price(token0_address, chain_id)
            price1, quality1 = await self.get_token_price(token1_address, chain_id)
            
            # Check if we have valid prices
            if price0 is None and price1 is None:
                return None, DataQuality.ERROR
            
            # Update quality
            if quality0 == DataQuality.ERROR or quality1 == DataQuality.ERROR:
                quality = DataQuality.ERROR
            elif quality0 == DataQuality.STALE or quality1 == DataQuality.STALE:
                quality = DataQuality.STALE
            
            # Use 0 for missing prices
            price0 = price0 or 0
            price1 = price1 or 0
            
            # Calculate LP price
            total_value = (reserve0_norm * price0) + (reserve1_norm * price1)
            lp_price = total_value / total_supply_norm if total_supply_norm > 0 else 0
            
            if lp_price > 0:
                self._set_cached_lp(cache_key, lp_price, quality)
                return lp_price, quality
            
            return None, DataQuality.ERROR
            
        except Exception as e:
            logger.error(f"Failed to calculate LP price for {lp_address}: {e}")
            
            if cache_key in self._lp_cache:
                return self._lp_cache[cache_key].value, DataQuality.STALE
            
            return None, DataQuality.ERROR
    
    # ====================
    # Beefy-style Batch Endpoints
    # ====================
    
    def get_all_token_prices(self, chain_id: int) -> Dict[str, Any]:
        """
        Get all cached token prices for a chain (Beefy /prices style).
        Returns: {address: price} map
        """
        result = {}
        prefix = f"{chain_id}:"
        
        for key, entry in self._token_cache.items():
            if key.startswith(prefix):
                address = key[len(prefix):]
                age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
                if age < self.STALE_THRESHOLD:
                    result[address] = entry.value
        
        return result
    
    def get_all_lp_prices(self, chain_id: int) -> Dict[str, Any]:
        """
        Get all cached LP prices for a chain (Beefy /lps style).
        Returns: {address: price} map
        """
        result = {}
        prefix = f"{chain_id}:"
        
        for key, entry in self._lp_cache.items():
            if key.startswith(prefix):
                address = key[len(prefix):]
                age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
                if age < self.STALE_THRESHOLD:
                    result[address] = entry.value
        
        return result
    
    async def refresh_prices_for_vaults(
        self,
        w3: Web3,
        vaults: List[Dict],
        chain_id: int
    ) -> Dict[str, DataQuality]:
        """
        Refresh prices for all tokens and LPs used by vaults.
        Returns quality status per address.
        """
        quality_map = {}
        
        # Collect all unique addresses
        token_addresses = set()
        lp_addresses = set()
        
        for vault in vaults:
            if vault.get('chainId') == chain_id:
                want = vault.get('wantAddress', '')
                reward = vault.get('rewardToken', '')
                
                if want:
                    lp_addresses.add(want)
                if reward:
                    token_addresses.add(reward)
        
        # Fetch LP prices (which also fetches underlying token prices)
        for lp_addr in lp_addresses:
            price, quality = await self.get_lp_price(w3, lp_addr, chain_id)
            quality_map[lp_addr.lower()] = quality
        
        # Fetch remaining token prices
        for token_addr in token_addresses:
            if token_addr.lower() not in quality_map:
                price, quality = await self.get_token_price(token_addr, chain_id)
                quality_map[token_addr.lower()] = quality
        
        return quality_map
    
    def clear_cache(self):
        """Clear all caches."""
        self._token_cache.clear()
        self._lp_cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now(timezone.utc)
        
        def count_by_freshness(cache: Dict) -> Dict[str, int]:
            fresh = stale = expired = 0
            for entry in cache.values():
                age = (now - entry.timestamp).total_seconds()
                if age < self.CACHE_TTL:
                    fresh += 1
                elif age < self.STALE_THRESHOLD:
                    stale += 1
                else:
                    expired += 1
            return {"fresh": fresh, "stale": stale, "expired": expired}
        
        token_stats = count_by_freshness(self._token_cache)
        lp_stats = count_by_freshness(self._lp_cache)
        
        return {
            "token_prices": {
                "total": len(self._token_cache),
                **token_stats
            },
            "lp_prices": {
                "total": len(self._lp_cache),
                **lp_stats
            },
            "decimals_cached": len(self._decimals_cache),
            "rate_limiter_tokens": self._rate_limiter.tokens,
        }


# Global singleton instance
_price_service: Optional[PriceService] = None


def get_price_service() -> PriceService:
    """Get the global price service instance."""
    global _price_service
    if _price_service is None:
        _price_service = PriceService()
    return _price_service
