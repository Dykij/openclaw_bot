"""Cron Job Scheduler + Proactive Engine — periodic and event-driven task execution.

Provides a lightweight wrapper around APScheduler for running
periodic bot tasks: memory GC, cache warmup, health checks, report
generation, and custom user-defined cron jobs.

Phase 7 addition: Proactive Engine
  - File system watcher (watchdog) monitors configured directories
    and dispatches analysis tasks through the pipeline.
  - RSS/feed checker periodically polls configured feeds and generates
    summaries or research tasks when new entries appear.

Usage:
    scheduler = OpenClawScheduler(config, pipeline, bot)
    await scheduler.start()
    ...
    await scheduler.shutdown()
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Dict, Optional

import structlog

if TYPE_CHECKING:
    from aiogram import Bot
    from src.pipeline_executor import PipelineExecutor

logger = structlog.get_logger("OpenClawScheduler")


class OpenClawScheduler:
    """APScheduler-based cron job runner for the OpenClaw bot."""

    def __init__(
        self,
        config: Dict[str, Any],
        pipeline: Optional["PipelineExecutor"] = None,
        bot: Optional["Bot"] = None,
    ) -> None:
        self.config = config
        self.pipeline = pipeline
        self.bot = bot
        self._scheduler: Any = None  # AsyncIOScheduler instance
        self._running = False

    async def start(self) -> None:
        """Initialize and start the APScheduler with configured jobs."""
        try:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
        except ImportError:
            logger.warning("APScheduler not installed — scheduler disabled. Install with: pip install apscheduler")
            return

        self._scheduler = AsyncIOScheduler()
        jobs_config = self.config.get("scheduler", {}).get("jobs", [])

        # Built-in jobs
        self._scheduler.add_job(
            self._memory_gc,
            trigger=IntervalTrigger(hours=24),
            id="memory_gc",
            name="Memory Garbage Collection",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._health_check,
            trigger=IntervalTrigger(minutes=30),
            id="health_check",
            name="Health Check",
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._memory_decay,
            trigger=IntervalTrigger(hours=6),
            id="memory_decay",
            name="Memory Importance Decay",
            replace_existing=True,
        )

        # User-defined cron jobs from config
        for job_def in jobs_config:
            job_id = job_def.get("id", "")
            cron_expr = job_def.get("cron", "")
            action = job_def.get("action", "")
            if not (job_id and cron_expr and action):
                logger.warning("Invalid job definition, skipping", job=job_def)
                continue

            try:
                trigger = CronTrigger.from_crontab(cron_expr)
                self._scheduler.add_job(
                    self._run_custom_job,
                    trigger=trigger,
                    id=job_id,
                    name=job_def.get("name", job_id),
                    replace_existing=True,
                    kwargs={"action": action, "job_id": job_id},
                )
                logger.info("Custom cron job registered", job_id=job_id, cron=cron_expr)
            except Exception as e:
                logger.error("Failed to register cron job", job_id=job_id, error=str(e))

        self._scheduler.start()
        self._running = True
        logger.info("Scheduler started", builtin_jobs=3, custom_jobs=len(jobs_config))

        # Phase 7: Proactive Engine (file watcher + RSS)
        await self._start_proactive_engine()

    async def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler and self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False
            logger.info("Scheduler shut down")

    # --- Built-in Jobs ---

    async def _memory_gc(self) -> None:
        """Run memory garbage collection."""
        try:
            from src.memory_gc import MemoryGarbageCollector
            gc = MemoryGarbageCollector()
            gc.run()
            logger.info("Scheduled memory GC completed")
        except Exception as e:
            logger.error("Scheduled memory GC failed", error=str(e))

    async def _health_check(self) -> None:
        """Periodic health check — log inference metrics and system status."""
        try:
            if self.pipeline and hasattr(self.pipeline, "metrics_collector"):
                metrics = self.pipeline.metrics_collector.get_metrics()
                logger.info(
                    "Health check",
                    total_requests=metrics.total_requests,
                    avg_tps=round(metrics.avg_tps, 1),
                    avg_ttft_ms=round(metrics.avg_ttft_ms, 1),
                    cache_hit_rate=round(metrics.cache_hit_rate, 3),
                )
        except Exception as e:
            logger.error("Health check failed", error=str(e))

    async def _memory_decay(self) -> None:
        """Apply time-based importance decay + garbage collection to SuperMemory."""
        try:
            from src.supermemory import SuperMemory
            mem = SuperMemory()
            mem.initialize()
            mem.decay(factor=0.95)
            gc_stats = mem.gc()
            logger.info("Scheduled memory decay + GC completed", **gc_stats)
        except Exception as e:
            logger.error("Scheduled memory decay failed", error=str(e))

    async def _run_custom_job(self, action: str, job_id: str) -> None:
        """Execute a custom user-defined cron action through the pipeline."""
        if not self.pipeline:
            logger.warning("Pipeline not available for custom job", job_id=job_id)
            return
        try:
            logger.info("Running custom cron job", job_id=job_id, action=action[:100])
            result = await self.pipeline.execute(
                prompt=action,
                brigade="OpenClaw",
                task_type="general",
            )
            status = result.get("status", "unknown")
            logger.info("Custom cron job completed", job_id=job_id, status=status)
        except Exception as e:
            logger.error("Custom cron job failed", job_id=job_id, error=str(e))

    def add_job(
        self,
        func: Callable[..., Coroutine],
        cron: str,
        job_id: str,
        name: str = "",
    ) -> bool:
        """Programmatically add a cron job at runtime."""
        if not self._scheduler:
            logger.warning("Scheduler not started — cannot add job")
            return False
        try:
            from apscheduler.triggers.cron import CronTrigger
            trigger = CronTrigger.from_crontab(cron)
            self._scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                name=name or job_id,
                replace_existing=True,
            )
            logger.info("Job added at runtime", job_id=job_id, cron=cron)
            return True
        except Exception as e:
            logger.error("Failed to add job", job_id=job_id, error=str(e))
            return False

    # --- Phase 7: Proactive Engine ---

    async def _start_proactive_engine(self) -> None:
        """Initialize file watcher and RSS checker if enabled in config."""
        proactive_cfg = self.config.get("proactive", {})
        if not proactive_cfg.get("enabled", False):
            logger.info("Proactive Engine disabled in config")
            return

        # File system watcher
        watch_dirs = proactive_cfg.get("watch_dirs", [])
        if watch_dirs:
            self._start_file_watcher(watch_dirs)

        # RSS feed checker
        feeds = proactive_cfg.get("rss_feeds", [])
        if feeds and self._scheduler:
            from apscheduler.triggers.interval import IntervalTrigger
            interval_min = proactive_cfg.get("rss_interval_minutes", 60)
            self._scheduler.add_job(
                self._check_rss_feeds,
                trigger=IntervalTrigger(minutes=interval_min),
                id="rss_checker",
                name="Proactive RSS Feed Checker",
                replace_existing=True,
                kwargs={"feeds": feeds},
            )
            logger.info("RSS feed checker registered", feeds=len(feeds), interval_min=interval_min)

        logger.info("Proactive Engine started", watch_dirs=len(watch_dirs), rss_feeds=len(feeds))

    def _start_file_watcher(self, watch_dirs: list[str]) -> None:
        """Start watchdog observer for file changes that trigger analysis."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

            class _ProactiveHandler(FileSystemEventHandler):
                def __init__(self, scheduler: "OpenClawScheduler") -> None:
                    self._scheduler = scheduler
                    self._last_event: dict[str, float] = {}
                    self._debounce_sec = 30.0

                def on_modified(self, event: FileModifiedEvent) -> None:
                    if event.is_directory:
                        return
                    self._handle(event.src_path, "modified")

                def on_created(self, event: FileCreatedEvent) -> None:
                    if event.is_directory:
                        return
                    self._handle(event.src_path, "created")

                def _handle(self, path: str, kind: str) -> None:
                    now = time.time()
                    if now - self._last_event.get(path, 0) < self._debounce_sec:
                        return
                    self._last_event[path] = now
                    # Schedule analysis via pipeline (fire-and-forget)
                    loop = asyncio.get_event_loop()
                    loop.call_soon_threadsafe(
                        asyncio.ensure_future,
                        self._scheduler._handle_file_event(path, kind),
                    )

            observer = Observer()
            handler = _ProactiveHandler(self)
            for d in watch_dirs:
                if os.path.isdir(d):
                    observer.schedule(handler, d, recursive=True)
                    logger.info("Watching directory", path=d)
                else:
                    logger.warning("Watch dir does not exist", path=d)
            observer.daemon = True
            observer.start()
            self._file_observer = observer
            logger.info("File watcher started", dirs=len(watch_dirs))
        except ImportError:
            logger.warning("watchdog not installed — file watcher disabled")
        except Exception as e:
            logger.error("Failed to start file watcher", error=str(e))

    async def _handle_file_event(self, path: str, kind: str) -> None:
        """React to a file change by dispatching an analysis task."""
        if not self.pipeline:
            return
        try:
            prompt = (
                f"[Proactive] File {kind}: {path}\n"
                f"Analyze this file change and determine if any action is needed. "
                f"If no action is required, respond with 'No action needed.'"
            )
            result = await self.pipeline.execute(
                prompt=prompt,
                brigade="OpenClaw",
                task_type="proactive",
            )
            status = result.get("status", "unknown") if isinstance(result, dict) else "unknown"
            logger.info("Proactive file analysis done", path=path, kind=kind, status=status)
        except Exception as e:
            logger.error("Proactive file analysis failed", path=path, error=str(e))

    async def _check_rss_feeds(self, feeds: list[str]) -> None:
        """Poll RSS feeds and dispatch summaries for new entries."""
        if not self.pipeline:
            return
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed — RSS checker disabled")
            return

        if not hasattr(self, "_rss_seen"):
            self._rss_seen: set[str] = set()

        for feed_url in feeds:
            try:
                parsed = feedparser.parse(feed_url)
                new_entries = []
                for entry in parsed.entries[:5]:
                    entry_id = entry.get("id", entry.get("link", ""))
                    if entry_id and entry_id not in self._rss_seen:
                        self._rss_seen.add(entry_id)
                        new_entries.append(f"- {entry.get('title', 'No title')}: {entry.get('link', '')}")

                if new_entries:
                    prompt = (
                        f"[Proactive RSS] New entries from {feed_url}:\n"
                        + "\n".join(new_entries[:3]) + "\n\n"
                        "Summarize these entries and determine if any are relevant to ongoing work."
                    )
                    await self.pipeline.execute(
                        prompt=prompt,
                        brigade="OpenClaw",
                        task_type="proactive",
                    )
                    logger.info("RSS feed processed", feed=feed_url, new_entries=len(new_entries))
            except Exception as e:
                logger.error("RSS feed check failed", feed=feed_url, error=str(e))
