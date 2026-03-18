import asyncio
import logging
import orjson
import redis.asyncio as redis
from typing import Dict

logger = logging.getLogger("RedisState")
logger.setLevel(logging.INFO)

class InMemoryOrderBook:
    """
    Maintains the ultra-low latency In-Memory Order Book state using Redis.
    The CuPy Bellman-Ford scanner fetches graph edges directly from here.
    """
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self.pool = None
        self._cache = None
        
    async def connect(self):
        self.pool = redis.ConnectionPool.from_url(self.redis_url, max_connections=10)
        self._cache = redis.Redis(connection_pool=self.pool)
        logger.info(f"Connected to Redis state memory at {self.redis_url}")

    async def update_edge(self, source: str, target: str, exchange_rate: float, trading_fee: float):
        """
        Updates the specific market traversal edge.
        O(1) dictionary style access for the HFT scanner.
        """
        key = f"edge:{source}_{target}"
        payload = orjson.dumps({
            "source": source,
            "target": target,
            "exchange_rate": exchange_rate,
            "trading_fee": trading_fee,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        # O(1) SET
        await self._cache.set(key, payload)

    async def fetch_all_edges(self) -> list[Dict[str, any]]:
        """
        Fetches the complete snapshot of all known order book edges instantly.
        Returns them as a list of dictionaries for ScannerV3.build_graph()
        """
        edges = []
        try:
            # We use SCAN instead of KEYS for non-blocking iteration in production Redis
            cursor = b'0'
            while cursor:
                cursor, keys = await self._cache.scan(cursor=cursor, match="edge:*", count=1000)
                if not keys:
                    break
                    
                # MGET for maximum throughput
                values_raw = await self._cache.mget(keys)
                for val in values_raw:
                    if val:
                        edges.append(orjson.loads(val))
                        
        except Exception as e:
            logger.error(f"Failed to fetch Redis edges: {e}")
            
        return edges

    async def close(self):
        if self.pool:
            await self.pool.disconnect()
            
if __name__ == "__main__":
    pass
