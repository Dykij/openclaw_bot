"""Smoke test: MCP client initialization via PipelineExecutor."""
import json


async def test_mcp_init():
    from src.pipeline._core import PipelineExecutor

    cfg = json.load(open("config/openclaw_config.json", encoding="utf-8"))
    pipeline = PipelineExecutor(config=cfg)
    await pipeline.initialize()

    assert hasattr(pipeline, "openclaw_mcp"), "openclaw_mcp not initialized"
    assert pipeline.openclaw_mcp.available_tools_openai is not None
    assert len(pipeline.openclaw_mcp._tool_route_map) > 0, "No tools registered"
