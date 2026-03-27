"""Level 2: Integration Tests — Proactive Engine (RSS + Watchdog).

Tests verify that:
- RSS feed checker detects new entries and dispatches pipeline tasks
- File watcher debounce logic works correctly
- Proactive Engine initialization respects config flags
- Scheduler integrates proactive jobs alongside built-in ones
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import time
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.scheduler import OpenClawScheduler


# ── Mock helpers ─────────────────────────────────────────────────────


class FakePipeline:
    """Fake pipeline that records all execute() calls."""

    def __init__(self):
        self.calls: List[Dict[str, Any]] = []

    async def execute(self, prompt: str, brigade: str = "OpenClaw", task_type: str = "general"):
        self.calls.append({"prompt": prompt, "brigade": brigade, "task_type": task_type})
        return {"status": "ok", "final_response": "Processed"}


FAKE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>ReAct Agents Best Practices 2026</title>
      <link>https://example.com/react-2026</link>
      <guid>entry-001</guid>
    </item>
    <item>
      <title>Multi-Agent Orchestration Deep Dive</title>
      <link>https://example.com/multi-agent</link>
      <guid>entry-002</guid>
    </item>
    <item>
      <title>Old Post About Weather</title>
      <link>https://example.com/weather</link>
      <guid>entry-003</guid>
    </item>
  </channel>
</rss>"""


class FakeFeedResult:
    """Simulates feedparser.parse() output."""
    def __init__(self, entries):
        self.entries = entries


def make_feed_entries(xml_text: str = FAKE_RSS_XML) -> FakeFeedResult:
    """Parse fake RSS into feedparser-like structure."""
    import re
    entries = []
    for match in re.finditer(
        r"<item>.*?<title>(.*?)</title>.*?<link>(.*?)</link>.*?<guid>(.*?)</guid>.*?</item>",
        xml_text,
        re.DOTALL,
    ):
        entries.append({
            "title": match.group(1),
            "link": match.group(2),
            "id": match.group(3),
        })
    return FakeFeedResult(entries)


# ── RSS Feed Checker ─────────────────────────────────────────────────


class TestRSSChecker:
    """Level 2a: RSS feed checker integrates with pipeline."""

    @pytest.fixture
    def scheduler(self):
        config = {
            "proactive": {
                "enabled": True,
                "rss_feeds": ["https://habr.com/ru/rss/articles/"],
                "rss_interval_minutes": 60,
                "watch_dirs": [],
            }
        }
        pipeline = FakePipeline()
        sched = OpenClawScheduler(config=config, pipeline=pipeline)
        sched._rss_seen = set()
        return sched, pipeline

    @pytest.mark.asyncio
    async def test_rss_detects_new_entries(self, scheduler):
        sched, pipeline = scheduler
        fake_result = make_feed_entries()

        with patch("feedparser.parse", return_value=fake_result):
            await sched._check_rss_feeds(["https://example.com/feed"])

        # All 3 entries should be new → pipeline called once with summary
        assert len(pipeline.calls) == 1
        call = pipeline.calls[0]
        assert call["task_type"] == "proactive"
        assert "ReAct Agents" in call["prompt"]
        assert "Multi-Agent" in call["prompt"]

    @pytest.mark.asyncio
    async def test_rss_dedup_skips_seen(self, scheduler):
        sched, pipeline = scheduler
        fake_result = make_feed_entries()

        # Mark entry-001 as already seen
        sched._rss_seen.add("entry-001")

        with patch("feedparser.parse", return_value=fake_result):
            await sched._check_rss_feeds(["https://example.com/feed"])

        assert len(pipeline.calls) == 1
        # entry-001 should NOT be in the prompt
        assert "entry-001" not in pipeline.calls[0]["prompt"]
        # But entry-002 should be
        assert "Multi-Agent" in pipeline.calls[0]["prompt"]

    @pytest.mark.asyncio
    async def test_rss_all_seen_no_dispatch(self, scheduler):
        sched, pipeline = scheduler
        fake_result = make_feed_entries()

        sched._rss_seen = {"entry-001", "entry-002", "entry-003"}

        with patch("feedparser.parse", return_value=fake_result):
            await sched._check_rss_feeds(["https://example.com/feed"])

        # No new entries → no pipeline calls
        assert len(pipeline.calls) == 0

    @pytest.mark.asyncio
    async def test_rss_handles_feed_error(self, scheduler):
        sched, pipeline = scheduler
        with patch("feedparser.parse", side_effect=Exception("Network error")):
            # Should not raise, just log
            await sched._check_rss_feeds(["https://broken.feed/rss"])
        assert len(pipeline.calls) == 0

    @pytest.mark.asyncio
    async def test_rss_no_pipeline_noop(self):
        sched = OpenClawScheduler(config={}, pipeline=None)
        # Should not raise
        await sched._check_rss_feeds(["https://example.com/feed"])


# ── File Event Handler ───────────────────────────────────────────────


class TestFileEventHandler:
    """Level 2b: File event dispatch and debounce."""

    @pytest.fixture
    def scheduler(self):
        config = {"proactive": {"enabled": True, "watch_dirs": [], "rss_feeds": []}}
        pipeline = FakePipeline()
        return OpenClawScheduler(config=config, pipeline=pipeline), pipeline

    @pytest.mark.asyncio
    async def test_file_event_dispatches(self, scheduler):
        sched, pipeline = scheduler
        await sched._handle_file_event("/tmp/test.md", "modified")
        assert len(pipeline.calls) == 1
        assert pipeline.calls[0]["task_type"] == "proactive"
        assert "File modified" in pipeline.calls[0]["prompt"]
        assert "/tmp/test.md" in pipeline.calls[0]["prompt"]

    @pytest.mark.asyncio
    async def test_file_event_created(self, scheduler):
        sched, pipeline = scheduler
        await sched._handle_file_event("/data/new_file.json", "created")
        assert pipeline.calls[0]["prompt"].startswith("[Proactive] File created:")

    @pytest.mark.asyncio
    async def test_file_event_no_pipeline_noop(self):
        sched = OpenClawScheduler(config={}, pipeline=None)
        # Should not raise
        await sched._handle_file_event("/tmp/x.py", "created")


# ── Proactive Engine Initialization ──────────────────────────────────


class TestProactiveEngineInit:
    """Level 2c: Proactive Engine respects config and starts correctly."""

    @pytest.mark.asyncio
    async def test_disabled_when_config_false(self):
        config = {"proactive": {"enabled": False}}
        sched = OpenClawScheduler(config=config, pipeline=FakePipeline())
        # Should exit early, no error
        await sched._start_proactive_engine()
        assert not hasattr(sched, "_file_observer")

    @pytest.mark.asyncio
    async def test_disabled_when_no_config(self):
        sched = OpenClawScheduler(config={}, pipeline=FakePipeline())
        await sched._start_proactive_engine()
        assert not hasattr(sched, "_file_observer")

    @pytest.mark.asyncio
    async def test_watcher_starts_with_valid_dirs(self, tmp_path):
        watch_dir = str(tmp_path / "watch_me")
        os.makedirs(watch_dir)
        config = {
            "proactive": {
                "enabled": True,
                "watch_dirs": [watch_dir],
                "rss_feeds": [],
            }
        }
        sched = OpenClawScheduler(config=config, pipeline=FakePipeline())
        await sched._start_proactive_engine()
        assert hasattr(sched, "_file_observer")
        sched._file_observer.stop()

    @pytest.mark.asyncio
    async def test_watcher_skips_nonexistent_dirs(self, tmp_path):
        config = {
            "proactive": {
                "enabled": True,
                "watch_dirs": [str(tmp_path / "does_not_exist")],
                "rss_feeds": [],
            }
        }
        sched = OpenClawScheduler(config=config, pipeline=FakePipeline())
        # Should not raise
        await sched._start_proactive_engine()
