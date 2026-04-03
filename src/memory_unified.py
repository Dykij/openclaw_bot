"""
Unified Memory Module — single entry point for all memory subsystems.

Consolidates:
- memory_enhanced.py: TieredMemoryManager, MemoryImportanceScorer, EpisodicMemory
- memory_gc.py: MemoryGarbageCollector (Anchored Iterative Context Compressor)

Usage:
    from src.memory_unified import TieredMemoryManager, MemoryGarbageCollector, EpisodicMemory
"""

from src.memory_enhanced import (
    EpisodeRecord,
    EpisodicMemory,
    MemoryImportanceScorer,
    MemoryItem,
    MemoryStats,
    TieredMemoryManager,
    WorkingMemoryPage,
)
from src.memory_gc import MemoryGarbageCollector

__all__ = [
    "TieredMemoryManager",
    "MemoryImportanceScorer",
    "MemoryItem",
    "MemoryStats",
    "WorkingMemoryPage",
    "EpisodicMemory",
    "EpisodeRecord",
    "MemoryGarbageCollector",
]
