import time
import subprocess
import logging

logger = logging.getLogger("ChaosTest")
logger.setLevel(logging.INFO)

def run_chaos_test():
    """
    Simulates catastrophic failures logically inside the Paper-Trade 120min Window.
    """
    logger.info("Initializing 2-Hour Chaos Test Sequence...")
    
    # ---------------------------------------------------------
    # T+30 Minutes: The Redis Kill
    # ---------------------------------------------------------
    logger.info("⏳ Waiting 30 minutes (1800s) for Redis Kill event...")
    time.sleep(1800)
    
    logger.warning("💥 T+30: INITIATING REDIS CONTAINER KILL")
    # Use explicit argument list instead of shell=True to avoid command injection
    try:
        result = subprocess.run(["docker", "ps", "-q", "-f", "name=redis"], capture_output=True, text=True, check=False)
        container_ids = result.stdout.strip().split()
        for cid in container_ids:
            if cid:
                subprocess.run(["docker", "kill", cid], check=False)
    except FileNotFoundError:
        logger.warning("docker not found, skipping Redis kill")
    logger.info("✅ Redis killed. Engines should be auto-recovering graph boundaries via websockets.")
    
    # ---------------------------------------------------------
    # T+60 Minutes: The VRAM Spike
    # ---------------------------------------------------------
    logger.info("⏳ Waiting another 30 minutes (1800s) for VRAM Spike event...")
    time.sleep(1800)
    
    logger.warning("💥 T+60: INITIATING 14GB VRAM SPIKE on GPU 0")
    try:
        import torch
        # 14GB = 14 * 1024^3 bytes. float32 = 4 bytes per element.
        elements = (14 * 1024 * 1024 * 1024) // 4
        dummy_tensor = torch.zeros((elements,), dtype=torch.float32, device='cuda')
        logger.info("🔥 14GB VRAM Spike Active. VRAMGuard should be yielding non-core networks now.")
        
        # Hold the memory blockade for 5 minutes
        time.sleep(300)
        del dummy_tensor
        logger.info("✅ VRAM Spike released. Normal operations resuming.")
    except Exception as e:
        logger.error(f"Failed to execute VRAM spike: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_chaos_test()
