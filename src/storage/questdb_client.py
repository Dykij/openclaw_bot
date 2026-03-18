import asyncio
import logging
import orjson
import aiohttp
from datetime import datetime

logger = logging.getLogger("QuestDB")
logger.setLevel(logging.INFO)

class QuestDBClient:
    """
    Time-Series Persistence client.
    - Uses ILP (InfluxDB Line Protocol) over TCP for ultra-fast INSERTS.
    - Uses REST API for massive batch QUERIES (HMM Baum-Welch calibration).
    """
    def __init__(self, ilp_host: str = "127.0.0.1", ilp_port: int = 9009, rest_url: str = "http://127.0.0.1:9000"):
        self.ilp_host = ilp_host
        self.ilp_port = ilp_port
        self.rest_url = rest_url
        self.ilp_writer = None

    async def connect_ilp(self):
        """Establish non-blocking TCP socket for ILP streams."""
        try:
            _, self.ilp_writer = await asyncio.open_connection(self.ilp_host, self.ilp_port)
            logger.info("Connected to QuestDB ILP port.")
        except Exception as e:
            logger.error(f"QuestDB ILP Connection failed: {e}")

    async def insert_tick_ilp(self, symbol: str, price: float, volume: float, side: str, hawkes: float, sentiment: float):
        """
        Fire-and-forget streaming over raw TCP using Influx Line Protocol.
        Does not block the python event loop waiting for DB transactions (WAL handles it).
        """
        if not self.ilp_writer:
            logger.warning("QuestDB writer missing, tick dropped.")
            return

        # ILP Format: table_name,tag1=val1 field1=val1,field2=val2 timestamp_ns
        timestamp_ns = int(datetime.utcnow().timestamp() * 1e9)
        
        # Tags (indexed strings) go before the space, Fields (metrics) go after
        line = f"market_ticks,symbol={symbol},side={side} price={price},volume={volume},hawkes_intensity={hawkes},llm_sentiment_score={sentiment} {timestamp_ns}\n"
        
        self.ilp_writer.write(line.encode('utf-8'))
        await self.ilp_writer.drain()

    async def query_historical_ticks(self, symbol: str, hours_back: int = 3) -> list:
        """
        REST API Query for HMM Baum-Welch offline re-calibration.
        Downloads millions of rows instantly into python arrays.
        """
        query = f"SELECT * FROM market_ticks WHERE symbol = '{symbol}' AND timestamp >= dateadd('h', -{hours_back}, now())"
        
        params = {'query': query, 'fmt': 'json'}
        
        async with aiohttp.ClientSession() as session:
            try:
                # QuestDB REST queries are blazing fast
                async with session.get(f"{self.rest_url}/exec", params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json(loads=orjson.loads)
                        dataset = data.get('dataset', [])
                        logger.info(f"Retrieved {len(dataset)} historical ticks for HMM Calibration.")
                        return dataset
                    else:
                        text = await resp.text()
                        logger.error(f"QuestDB Query failed: {text}")
            except Exception as e:
                logger.error(f"QuestDB communication error: {e}")
                
        return []

    async def close(self):
        if self.ilp_writer:
            self.ilp_writer.close()
            await self.ilp_writer.wait_closed()
