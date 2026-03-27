"""Boot utilities — environment setup, locking, config reloading, MCP init."""

from src.boot._env_setup import (
    LOCK_FILE,
    MODEL_LOAD_GAUGE,
    PROMPT_COUNTER,
    VRAM_GAUGE,
    ConfigReloader,
    acquire_lock,
    release_lock,
    setup_structlog,
)
from src.boot._mcp_init import configure_llm_and_pipeline

__all__ = [
    "LOCK_FILE",
    "MODEL_LOAD_GAUGE",
    "PROMPT_COUNTER",
    "VRAM_GAUGE",
    "ConfigReloader",
    "acquire_lock",
    "configure_llm_and_pipeline",
    "release_lock",
    "setup_structlog",
]
