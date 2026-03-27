import asyncio
import sys
import json
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
sys.path.append('src')
from mcp_client import OpenClawMCPClient

async def main():
    cfg = json.load(open('config/openclaw_config.json', encoding='utf-8'))
    mcp = OpenClawMCPClient(cfg, fs_allowed_dirs=['.'])
    await mcp.initialize()
    print("Available tools:")
    for k in mcp._tool_route_map.keys():
        print(f" - {k}")
    await mcp.cleanup()

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except:
            pass
    asyncio.run(main())
