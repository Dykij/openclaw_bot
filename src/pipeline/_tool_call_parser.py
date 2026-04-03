"""
Tool Call Text Parser — intercept XML/MD tool-call leakage from free models.

v14.2: Parses raw XML/Markdown tool-call tags that some models emit
instead of native JSON tool calls, executes them, and strips the raw
tags from the response.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ParsedToolCall:
    name: str
    arguments: Dict[str, Any]
    raw_match: str


# Patterns for tool-call leakage from various model families
_PATTERNS = [
    # <tool_call><function=name>{...}</function></tool_call>
    re.compile(
        r"<tool_call>\s*<function=(\w+)>(.*?)</function>\s*</tool_call>",
        re.DOTALL,
    ),
    # <function=name>{...}</function>
    re.compile(
        r"<function=(\w+)>(.*?)</function>",
        re.DOTALL,
    ),
    # <tool_call>{"name": ..., "arguments": ...}</tool_call>
    re.compile(
        r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
        re.DOTALL,
    ),
    # [TOOL_CALL] {...} [/TOOL_CALL]
    re.compile(
        r"\[TOOL_CALL\]\s*(\{.*?\})\s*\[/TOOL_CALL\]",
        re.DOTALL,
    ),
    # ```tool_call\n{...}\n```
    re.compile(
        r"```tool_call\s*\n(\{.*?\})\s*\n```",
        re.DOTALL,
    ),
    # <|tool_call|>{...}<|/tool_call|>
    re.compile(
        r"<\|tool_call\|>\s*(\{.*?\})\s*<\|/tool_call\|>",
        re.DOTALL,
    ),
]


def _safe_parse_json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def parse_tool_calls(text: str) -> List[ParsedToolCall]:
    """Parse raw tool-call tags from model output."""
    results: List[ParsedToolCall] = []
    seen_spans: list[tuple[int, int]] = []

    # Pattern 1 & 2: <function=name>{...}</function> (with or without <tool_call> wrapper)
    for pat in _PATTERNS[:2]:
        for m in pat.finditer(text):
            span = m.span()
            if any(s[0] <= span[0] < s[1] for s in seen_spans):
                continue
            seen_spans.append(span)
            name = m.group(1)
            args = _safe_parse_json(m.group(2))
            results.append(ParsedToolCall(name=name, arguments=args, raw_match=m.group(0)))

    # Patterns 3-6: JSON-body patterns
    for pat in _PATTERNS[2:]:
        for m in pat.finditer(text):
            span = m.span()
            if any(s[0] <= span[0] < s[1] for s in seen_spans):
                continue
            seen_spans.append(span)
            body = _safe_parse_json(m.group(1))
            name = body.get("name", "unknown")
            args = body.get("arguments", {})
            results.append(ParsedToolCall(name=name, arguments=args, raw_match=m.group(0)))

    return results


def has_tool_calls(text: str) -> bool:
    """Quick check whether text contains tool-call tags."""
    return len(parse_tool_calls(text)) > 0


def strip_tool_calls(text: str, calls: List[ParsedToolCall]) -> str:
    """Remove raw tool-call tags from text."""
    for call in calls:
        text = text.replace(call.raw_match, "")
    return text.strip()


def format_observations(results: List[Dict[str, Any]]) -> str:
    """Format tool execution results for injection into context."""
    parts: list[str] = []
    for r in results:
        status = "✅" if r.get("success") else "❌"
        tool = r.get("tool", "unknown")
        output = r.get("output", "")
        parts.append(f"{status} [{tool}]: {output}")
    return "\n".join(parts)


async def execute_parsed_tool_calls(
    calls: List[ParsedToolCall],
    mcp_client,
    sandbox,
) -> List[Dict[str, Any]]:
    """Execute parsed tool calls via MCP client or sandbox."""
    results: List[Dict[str, Any]] = []
    for call in calls:
        try:
            if mcp_client and hasattr(mcp_client, "call_tool"):
                result = await mcp_client.call_tool(call.name, call.arguments)
                results.append({"tool": call.name, "success": True, "output": str(result)})
            elif sandbox and hasattr(sandbox, "execute"):
                result = await sandbox.execute(call.name, call.arguments)
                results.append({"tool": call.name, "success": True, "output": str(result)})
            else:
                results.append({"tool": call.name, "success": False, "output": f"No handler for tool '{call.name}'"})
        except Exception as e:
            logger.warning("Tool call execution failed", tool=call.name, error=str(e))
            results.append({"tool": call.name, "success": False, "output": str(e)})
    return results
