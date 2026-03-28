"""
Parsers package — Universal Research Engine for OpenClaw Bot v11.6.

All sources are accessed through the UniversalParser orchestrator or
individual SourceAdapter instances.
"""

from src.parsers.universal import (
    ArxivAdapter,
    GitHubAdapter,
    HabrAdapter,
    OpenAlexAdapter,
    RedditAdapter,
    ResearchItem,
    SemanticScholarAdapter,
    SourceAdapter,
    UniversalParser,
)

__all__ = [
    "UniversalParser",
    "ResearchItem",
    "SourceAdapter",
    "HabrAdapter",
    "GitHubAdapter",
    "RedditAdapter",
    "SemanticScholarAdapter",
    "ArxivAdapter",
    "OpenAlexAdapter",
]
