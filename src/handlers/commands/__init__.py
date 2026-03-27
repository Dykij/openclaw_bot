"""Decomposed command handlers — re-exports from src.bot_commands + new modules.

src.bot_commands/ contains the actual implementations (already decomposed).
This package provides a unified namespace and houses new handler modules
(_admin, _tools, _media, _ai_config) for future additions.
"""

# Re-export everything via the established src.bot_commands entry point
from src.bot_commands import (
    cmd_agent,
    cmd_agents,
    cmd_help,
    cmd_history,
    cmd_models,
    cmd_openrouter_test,
    cmd_perf,
    cmd_research,
    cmd_start,
    cmd_status,
    cmd_tailscale,
    cmd_test,
    cmd_test_all_models,
    handle_callback_query,
    handle_document,
    handle_photo,
    handle_unknown_command,
    handle_voice,
)

__all__ = [
    "cmd_agent",
    "cmd_agents",
    "cmd_help",
    "cmd_history",
    "cmd_models",
    "cmd_openrouter_test",
    "cmd_perf",
    "cmd_research",
    "cmd_start",
    "cmd_status",
    "cmd_tailscale",
    "cmd_test",
    "cmd_test_all_models",
    "handle_callback_query",
    "handle_document",
    "handle_photo",
    "handle_unknown_command",
    "handle_voice",
]
