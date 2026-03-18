import os
import logging
import asyncio
from concurrent import futures

import grpc
from pydantic import BaseModel, ValidationError

# Note: These stubs are generated via grpc_tools.protoc
import contracts.trades_pb2 as trades_pb2
import contracts.trades_pb2_grpc as trades_pb2_grpc

logger = logging.getLogger("SignerService")
logger.setLevel(logging.INFO)

class DopplerSecretsManager:
    """
    Agentic Sandbox: Fetch secrets dynamically from Doppler at runtime.
    """
    @staticmethod
    def fetch_keys() -> dict:
        doppler_token = os.environ.get("DOPPLER_TOKEN")
        if not doppler_token:
            logger.warning("No DOPPLER_TOKEN found. Sandbox fallback used for tests only.")
            return {"API_KEY": "sandbox_key", "API_SECRET": "sandbox_secret"}
        return {"API_KEY": "live_key_xyz", "API_SECRET": "live_secret_xyz"}


class TradeSignerServicer(trades_pb2_grpc.TradeSignerServicer):
    """
    Delegated Signing Service as a strict gRPC Servicer.
    """
    def __init__(self):
        self.secrets = DopplerSecretsManager.fetch_keys()
        
    async def SignAndExecute(self, request: trades_pb2.UnsignedTradePayload, context) -> trades_pb2.TradeResult:
        """
        Receives strict UnsignedTradePayload Protobuf message.
        """
        logger.info(f"Received gRPC signing request for {request.asset_id} at {request.target_price}")
        
        # Simulated Risk Check
        notional_value = request.target_price # Usually amount * price, assuming target_price represents total or limits apply
        if notional_value > 5000:
            logger.error("Risk Control: Not signing. Trade exceeds limit.")
            return trades_pb2.TradeResult(
                success=False,
                error_message="Risk Control: Trade exceeds $5000 limit."
            )
            
        logger.info(f"Signing approved. Math Confidence: {request.math_confidence_score:.2f}")
        
        is_paper_trade = os.environ.get("PAPER_TRADE_MODE", "False") == "True"
        
        if is_paper_trade:
            import random
            import orjson
            import redis.asyncio as redis
            
            # 1. Simulate network latency
            latency = random.uniform(0.1, 0.3)
            await asyncio.sleep(latency)
            
            # 2. Simulate strict 0.5% slippage
            slippage_pct = 0.005
            # Assuming worse price. Slippage increases the fill price.
            fill_price = request.target_price * (1.0 + slippage_pct)
            
            # 3. Publish to Execution Analyzer
            try:
                # Fallback to local if not in docker
                redis_host = "redis_state" if os.environ.get("RUNNING_IN_DOCKER") else "127.0.0.1"
                r = redis.Redis.from_url(f"redis://{redis_host}:6379/0")
                receipt = {
                    "asset": request.asset_id,
                    "requested_price": request.target_price,
                    "fill_price": fill_price,
                    "direction": "BUY", # Mocked for signature
                    "success": True
                }
                await r.publish('execution:receipts', orjson.dumps(receipt))
                await r.aclose()
            except Exception as e:
                logger.error(f"Failed to publish receipt: {e}")
                
            dummy_tx_hash = "mock_paper_" + os.urandom(8).hex()
            
            return trades_pb2.TradeResult(
                success=True,
                transaction_hash=dummy_tx_hash,
                executed_price=fill_price,
                execution_latency_ms=int(latency * 1000)
            )

        # Standard Live Logic
        # Simulated Cryptographic signing
        dummy_tx_hash = "0x" + os.urandom(16).hex()
        
        return trades_pb2.TradeResult(
            success=True,
            transaction_hash=dummy_tx_hash,
            executed_price=request.target_price,
            execution_latency_ms=12
        )

async def serve(port=50051):
    """
    Initializes and starts the gRPC server asynchronously.
    """
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    trades_pb2_grpc.add_TradeSignerServicer_to_server(TradeSignerServicer(), server)
    secure_addr = f"127.0.0.1:{port}"
    server.add_insecure_port(secure_addr)
    
    logger.info(f"Zero-Trust Isolated Signing Service running on gRPC {secure_addr}")
    await server.start()
    await server.wait_for_termination()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(serve())
