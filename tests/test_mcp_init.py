import sys
import os
import asyncio
import json

from src.pipeline_executor import PipelineExecutor

async def main():
    cfg = json.load(open("config/openclaw_config.json", encoding="utf-8"))
    pipeline = PipelineExecutor(config=cfg, vllm_url="http://localhost:8000/v1")
    
    print("Initializing...")
    await pipeline.initialize()
    print("Initialization Done.")
    
    print("OpenClaw MCP Tools:", pipeline.openclaw_mcp.available_tools_openai)
    print("OpenClaw MCP Route Map:", list(pipeline.openclaw_mcp._tool_route_map.keys()))

if __name__ == "__main__":
    asyncio.run(main())
