"""
Price Service - Reusable pricing module with caching and rate limiting.

Features:
- Token price fetching from CoinGecko
- Uniswap V2 LP token pricing
- In-memory cache with TTL
- Rate limiting for API calls
- Data quality tracking
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any
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
    
    Usage:
        service = PriceService()
        price, quality = await service.get_token_price(address, chain_id)
        lp_price, quality = await service.get_lp_price(w3, lp_address, chain_id)
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
    
    # Testnet mock prices
    TESTNET_MOCK_PRICES = {
        "weth": 3000.0,
        "usdc": 1.0,
        "dai": 1.0,
        "default": 100.0,
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
        self._cache: Dict[str, CacheEntry] = {}
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
    
    def _cache_key(self, prefix: str, address: str, chain_id: int) -> str:
        """Generate cache key."""
        return f"{prefix}:{chain_id}:{address.lower()}"
    
    def _get_cached(self, key: str) -> Optional[Tuple[Any, DataQuality]]:
        """Get cached value with quality status."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        age = (datetime.now(timezone.utc) - entry.timestamp).total_seconds()
        
        if age < self.CACHE_TTL:
            return entry.value, DataQuality.OK
        elif age < self.STALE_THRESHOLD:
            return entry.value, DataQuality.STALE
        
        return None
    
    def _set_cached(self, key: str, value: Any, quality: DataQuality = DataQuality.OK):
        """Set cache entry."""
        self._cache[key] = CacheEntry(
            value=value,
            timestamp=datetime.now(timezone.utc),
            quality=quality
        )
    
    def get_token_decimals(self, w3: Web3, token_address: str) -> int:
        """Read decimals from ERC20 token contract."""
        if not token_address or not w3.is_address(token_address):
            return 18
        
        cache_key = self._cache_key("decimals", token_address, 0)
        cached = self._get_cached(cache_key)
        if cached:
            return cached[0]
        
        try:
            contract = w3.eth.contract(
                address=w3.to_checksum_address(token_address),
                abi=self.ERC20_ABI
            )
            decimals = contract.functions.decimals().call()
            self._set_cached(cache_key, decimals)
            return decimals
        except Exception as e:
            logger.warning(f"Failed to read decimals for {token_address}: {e}")
            return 18
    
    async def get_token_price(
        self,
        token_address: str,
        chain_id: int
    ) -> Tuple[float, DataQuality]:
        """
        Get token price in USD from CoinGecko.
        
        Returns:
            Tuple of (price_usd, data_quality)
        """
        if not token_address:
            return 0.0, DataQuality.ERROR
        
        cache_key = self._cache_key("price", token_address, chain_id)
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Testnet: return mock prices
        if chain_id == 84532:
            price = self.TESTNET_MOCK_PRICES.get("default", 100.0)
            self._set_cached(cache_key, price)
            return price, DataQuality.OK
        
        # Rate limit check
        if not await self._rate_limiter.acquire():
            # Return stale cache if available
            if cache_key in self._cache:
                return self._cache[cache_key].value, DataQuality.STALE
            return 0.0, DataQuality.ERROR
        
        # Try CoinGecko by ID first
        coingecko_id = self.BASE_MAINNET_TOKENS.get(token_address.lower())
        
        try:
            client = await self._get_client()
            
            if coingecko_id:
                # Fetch by CoinGecko ID
                url = "https://api.coingecko.com/api/v3/simple/price"
                params = {"ids": coingecko_id, "vs_currencies": "usd"}
                response = await client.get(url, params=params)
                
                if response.status_code == 200:
                    data = response.json()
                    if coingecko_id in data and "usd" in data[coingecko_id]:
                        price = data[coingecko_id]["usd"]
                        self._set_cached(cache_key, price)
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
                    self._set_cached(cache_key, price)
                    return price, DataQuality.OK
            
            # Rate limited
            if response.status_code == 429:
                logger.warning("CoinGecko rate limit hit")
                if cache_key in self._cache:
                    return self._cache[cache_key].value, DataQuality.STALE
                    
        except Exception as e:
            logger.error(f"CoinGecko API error for {token_address}: {e}")
        
        # Return stale cache or error
        if cache_key in self._cache:
            return self._cache[cache_key].value, DataQuality.STALE
        
        return 0.0, DataQuality.ERROR
    
    async def get_lp_price(
        self,
        w3: Web3,
        lp_address: str,
        chain_id: int
    ) -> Tuple[float, DataQuality]:
        """
        Calculate Uniswap V2-style LP token price.
        
        LP price = (reserve0 * price0 + reserve1 * price1) / totalSupply
        
        Returns:
            Tuple of (price_usd, data_quality)
        """
        if not lp_address or not w3.is_address(lp_address):
            return 0.0, DataQuality.ERROR
        
        cache_key = self._cache_key("lp", lp_address, chain_id)
        
        # Check cache
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Testnet: return mock price
        if chain_id == 84532:
            price = self.TESTNET_MOCK_PRICES.get("default", 100.0)
            self._set_cached(cache_key, price)
            return price, DataQuality.OK
        
        quality = DataQuality.OK
        
        try:
            lp_contract = w3.eth.contract(
                address=w3.to_checksum_address(lp_address),
                abi=self.UNISWAP_V2_PAIR_ABI
            )
            
            # Try to get reserves (this determines if it's an LP token)
            try:
                reserves = lp_contract.functions.getReserves().call()
                reserve0, reserve1, _ = reserves
            except Exception:
                # Not a Uniswap V2 LP - try direct price lookup
                return await self.get_token_price(lp_address, chain_id)
            
            # Get LP token data
            total_supply = lp_contract.functions.totalSupply().call()
            if total_supply == 0:
                return 0.0, DataQuality.ERROR
            
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
            
            # Update quality based on token prices
            if quality0 == DataQuality.ERROR or quality1 == DataQuality.ERROR:
                quality = DataQuality.ERROR
            elif quality0 == DataQuality.STALE or quality1 == DataQuality.STALE:
                quality = DataQuality.STALE
            
            if price0 == 0 and price1 == 0:
                return 0.0, DataQuality.ERROR
            
            # Calculate LP price
            total_value = (reserve0_norm * price0) + (reserve1_norm * price1)
            lp_price = total_value / total_supply_norm if total_supply_norm > 0 else 0
            
            self._set_cached(cache_key, lp_price, quality)
            return lp_price, quality
            
        except Exception as e:
            logger.error(f"Failed to calculate LP price for {lp_address}: {e}")
            
            # Return stale cache if available
            if cache_key in self._cache:
                return self._cache[cache_key].value, DataQuality.STALE
            
            return 0.0, DataQuality.ERROR
    
    async def get_prices_batch(
        self,
        token_addresses: list,
        chain_id: int
    ) -> Dict[str, Tuple[float, DataQuality]]:
        """
        Get prices for multiple tokens efficiently.
        Groups requests to minimize API calls.
        """
        results = {}
        uncached = []
        
        # Check cache first
        for addr in token_addresses:
            cache_key = self._cache_key("price", addr, chain_id)
            cached = self._get_cached(cache_key)
            if cached:
                results[addr.lower()] = cached
            else:
                uncached.append(addr)
        
        if not uncached:
            return results
        
        # Testnet: return mock prices
        if chain_id == 84532:
            for addr in uncached:
                price = self.TESTNET_MOCK_PRICES.get("default", 100.0)
                results[addr.lower()] = (price, DataQuality.OK)
                self._set_cached(self._cache_key("price", addr, chain_id), price)
            return results
        
        # Batch fetch from CoinGecko
        if not await self._rate_limiter.acquire():
            for addr in uncached:
                results[addr.lower()] = (0.0, DataQuality.ERROR)
            return results
        
        try:
            client = await self._get_client()
            
            # Fetch by contract addresses
            addresses_str = ",".join(a.lower() for a in uncached)
            url = "https://api.coingecko.com/api/v3/simple/token_price/base"
            params = {"contract_addresses": addresses_str, "vs_currencies": "usd"}
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                for addr in uncached:
                    addr_lower = addr.lower()
                    if addr_lower in data and "usd" in data[addr_lower]:
                        price = data[addr_lower]["usd"]
                        results[addr_lower] = (price, DataQuality.OK)
                        self._set_cached(self._cache_key("price", addr, chain_id), price)
                    else:
                        results[addr_lower] = (0.0, DataQuality.ERROR)
            else:
                for addr in uncached:
                    results[addr.lower()] = (0.0, DataQuality.ERROR)
                    
        except Exception as e:
            logger.error(f"Batch price fetch failed: {e}")
            for addr in uncached:
                results[addr.lower()] = (0.0, DataQuality.ERROR)
        
        return results
    
    def clear_cache(self):
        """Clear all cached prices."""
        self._cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        now = datetime.now(timezone.utc)
        fresh = 0
        stale = 0
        expired = 0
        
        for entry in self._cache.values():
            age = (now - entry.timestamp).total_seconds()
            if age < self.CACHE_TTL:
                fresh += 1
            elif age < self.STALE_THRESHOLD:
                stale += 1
            else:
                expired += 1
        
        return {
            "total_entries": len(self._cache),
            "fresh": fresh,
            "stale": stale,
            "expired": expired,
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
