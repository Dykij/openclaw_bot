"""
MCP Server: Web Search via DuckDuckGo (free, no API key required).
Exposes `web_search` and `web_fetch` tools for the OpenClaw pipeline.
Uses the `duckduckgo_search` library.
"""

import asyncio
import json
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import run_server
from mcp.types import TextContent, Tool

try:
    from duckduckgo_search import DDGS
except ImportError:
    print("[WebSearch MCP] ERROR: duckduckgo_search not installed. Run: pip install duckduckgo_search", file=sys.stderr)
    sys.exit(1)

server = Server("websearch-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description=(
                "Search the web using DuckDuckGo. Returns top results with title, URL, and snippet. "
                "Use for factual lookups, current events, documentation, and real-time data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                        "default": 5,
                    },
                    "region": {
                        "type": "string",
                        "description": "Region for search results (default: wt-wt for worldwide). Use ru-ru for Russian results.",
                        "default": "wt-wt",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="web_news_search",
            description=(
                "Search recent news articles via DuckDuckGo News. "
                "Returns headlines, sources, and publication dates."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "News search query"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of news results (default: 5)",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        ),
    ]


def _sync_search(query: str, max_results: int, region: str) -> list[dict[str, Any]]:
    """Run DuckDuckGo text search synchronously (library is sync-only)."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, region=region, max_results=min(max_results, 10)))
    return results


def _sync_news(query: str, max_results: int) -> list[dict[str, Any]]:
    """Run DuckDuckGo news search synchronously."""
    with DDGS() as ddgs:
        results = list(ddgs.news(query, max_results=min(max_results, 10)))
    return results


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "web_search":
        query = arguments["query"]
        max_results = arguments.get("max_results", 5)
        region = arguments.get("region", "wt-wt")

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_search, query, max_results, region)

        if not results:
            return [TextContent(type="text", text="No results found.")]

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'N/A')}**\n"
                f"   URL: {r.get('href', r.get('link', 'N/A'))}\n"
                f"   {r.get('body', r.get('snippet', ''))}"
            )
        return [TextContent(type="text", text="\n\n".join(formatted))]

    elif name == "web_news_search":
        query = arguments["query"]
        max_results = arguments.get("max_results", 5)

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _sync_news, query, max_results)

        if not results:
            return [TextContent(type="text", text="No news results found.")]

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(
                f"{i}. **{r.get('title', 'N/A')}**\n"
                f"   Source: {r.get('source', 'N/A')} | Date: {r.get('date', 'N/A')}\n"
                f"   URL: {r.get('url', r.get('link', 'N/A'))}\n"
                f"   {r.get('body', '')}"
            )
        return [TextContent(type="text", text="\n\n".join(formatted))]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    await run_server(server)


if __name__ == "__main__":
    asyncio.run(main())
