"""
ClawHub API Client — connects OpenClaw Bot to the ClawHub platform.

ClawHub is a marketplace/orchestration platform for AI agent tasks and skills.
This client handles:
- Authentication (API key based)
- Task polling (GET /tasks?status=pending)
- Result submission (POST /tasks/{id}/result)
- Skill registration (POST /skills/register)
- Health reporting (POST /agents/{id}/heartbeat)

All HTTP calls use aiohttp with retry logic and timeout handling.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
import structlog

logger = structlog.get_logger("ClawHub")


@dataclass
class ClawHubTask:
    """A task received from ClawHub."""
    task_id: str
    title: str
    description: str
    task_type: str = "general"  # "coding", "research", "parsing", "analysis"
    priority: int = 0
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    deadline: str = ""


@dataclass
class ClawHubSkill:
    """A skill/capability to register with ClawHub."""
    name: str
    description: str
    capabilities: List[str]
    model_tier: str = "balanced"
    max_concurrent: int = 1


class ClawHubClient:
    """Async client for ClawHub platform API.

    Usage:
        client = ClawHubClient(
            base_url="https://api.clawhub.ai",
            api_key=os.environ["CLAWHUB_API_KEY"],
            agent_id="openclaw-bot-001",
        )
        await client.initialize()
        tasks = await client.poll_tasks()
        for task in tasks:
            result = await process(task)
            await client.submit_result(task.task_id, result)
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        agent_id: str = "openclaw-bot",
        timeout_sec: int = 30,
        max_retries: int = 3,
    ):
        self._base_url = (base_url or os.environ.get("CLAWHUB_BASE_URL", "https://api.clawhub.ai")).rstrip("/")
        self._api_key = api_key or os.environ.get("CLAWHUB_API_KEY", "")
        self._agent_id = agent_id
        self._timeout_sec = timeout_sec
        self._max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None
        self._connected = False
        self._last_heartbeat = 0.0

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> bool:
        """Initialize the HTTP session and verify connectivity."""
        if not self._api_key:
            logger.warning("ClawHub API key not set — integration disabled")
            return False

        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Agent-ID": self._agent_id,
            },
            timeout=aiohttp.ClientTimeout(total=self._timeout_sec),
        )

        # Verify connectivity
        try:
            async with self._session.get(urljoin(self._base_url, "/health")) as resp:
                if resp.status == 200:
                    self._connected = True
                    logger.info("ClawHub connected", base_url=self._base_url)
                    return True
                logger.warning("ClawHub health check failed", status=resp.status)
        except Exception as e:
            logger.warning("ClawHub connection failed", error=str(e))

        return False

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None
            self._connected = False

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    async def poll_tasks(self, limit: int = 10) -> List[ClawHubTask]:
        """Poll ClawHub for pending tasks assigned to this agent."""
        if not self._connected or not self._session:
            return []

        url = urljoin(self._base_url, f"/api/v1/tasks?status=pending&agent_id={self._agent_id}&limit={limit}")
        data = await self._request("GET", url)
        if not data or "tasks" not in data:
            return []

        tasks = []
        for t in data["tasks"]:
            tasks.append(ClawHubTask(
                task_id=t.get("id", ""),
                title=t.get("title", ""),
                description=t.get("description", ""),
                task_type=t.get("type", "general"),
                priority=t.get("priority", 0),
                payload=t.get("payload", {}),
                created_at=t.get("created_at", ""),
                deadline=t.get("deadline", ""),
            ))
        logger.info("ClawHub tasks polled", count=len(tasks))
        return tasks

    async def submit_result(
        self,
        task_id: str,
        result: str,
        status: str = "completed",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Submit a task result back to ClawHub."""
        if not self._connected or not self._session:
            return False

        url = urljoin(self._base_url, f"/api/v1/tasks/{task_id}/result")
        payload = {
            "agent_id": self._agent_id,
            "status": status,
            "result": result,
            "metadata": metadata or {},
        }
        data = await self._request("POST", url, json_data=payload)
        success = data is not None and data.get("status") == "ok"
        if success:
            logger.info("ClawHub result submitted", task_id=task_id)
        return success

    # ------------------------------------------------------------------
    # Skill registration
    # ------------------------------------------------------------------

    async def register_skills(self, skills: List[ClawHubSkill]) -> bool:
        """Register agent skills/capabilities with ClawHub."""
        if not self._connected or not self._session:
            return False

        url = urljoin(self._base_url, "/api/v1/skills/register")
        payload = {
            "agent_id": self._agent_id,
            "skills": [
                {
                    "name": s.name,
                    "description": s.description,
                    "capabilities": s.capabilities,
                    "model_tier": s.model_tier,
                    "max_concurrent": s.max_concurrent,
                }
                for s in skills
            ],
        }
        data = await self._request("POST", url, json_data=payload)
        success = data is not None
        if success:
            logger.info("ClawHub skills registered", count=len(skills))
        return success

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    async def send_heartbeat(self, status: str = "active", metadata: Optional[Dict] = None) -> bool:
        """Send a heartbeat to ClawHub to indicate agent is alive."""
        if not self._connected or not self._session:
            return False

        url = urljoin(self._base_url, f"/api/v1/agents/{self._agent_id}/heartbeat")
        payload = {
            "status": status,
            "timestamp": time.time(),
            "metadata": metadata or {},
        }
        data = await self._request("POST", url, json_data=payload)
        if data is not None:
            self._last_heartbeat = time.time()
            return True
        return False

    # ------------------------------------------------------------------
    # Internal HTTP helper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make an HTTP request with retry logic."""
        if not self._session:
            return None

        for attempt in range(self._max_retries):
            try:
                if method == "GET":
                    async with self._session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.json()
                        if resp.status == 429:
                            wait = min(2 ** attempt * 2, 30)
                            logger.warning("ClawHub rate-limited", wait=wait)
                            await asyncio.sleep(wait)
                            continue
                        logger.warning("ClawHub HTTP error", status=resp.status, url=url)
                elif method == "POST":
                    async with self._session.post(url, json=json_data) as resp:
                        if resp.status in (200, 201):
                            return await resp.json()
                        if resp.status == 429:
                            wait = min(2 ** attempt * 2, 30)
                            await asyncio.sleep(wait)
                            continue
                        logger.warning("ClawHub HTTP error", status=resp.status, url=url)
            except asyncio.TimeoutError:
                logger.warning("ClawHub timeout", url=url, attempt=attempt + 1)
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                logger.warning("ClawHub request error", url=url, error=str(e))
                if attempt < self._max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        return None

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Get ClawHub client status."""
        return {
            "connected": self._connected,
            "base_url": self._base_url,
            "agent_id": self._agent_id,
            "last_heartbeat": self._last_heartbeat,
            "has_api_key": bool(self._api_key),
        }

    # ------------------------------------------------------------------
    # Marketplace: Skill Publishing & Fetching (Phase 8)
    # ------------------------------------------------------------------

    async def publish_skill(
        self,
        name: str,
        description: str,
        code: str,
        language: str = "python",
        tags: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Publish a tested sandbox skill to the ClawHub marketplace.

        Args:
            name: Display name of the skill.
            description: What it does.
            code: Source code of the skill.
            language: Programming language (python, bash, etc.).
            tags: Searchable tags.

        Returns:
            Server response dict on success, None on failure.
        """
        if not self._connected or not self._session:
            logger.warning("ClawHub not connected — cannot publish skill")
            return None

        import hashlib
        code_hash = hashlib.sha256(code.encode()).hexdigest()

        url = urljoin(self._base_url, "/api/v1/marketplace/skills")
        payload = {
            "agent_id": self._agent_id,
            "name": name,
            "description": description,
            "code": code,
            "language": language,
            "code_hash": code_hash,
            "tags": tags or [],
        }
        data = await self._request("POST", url, json_data=payload)
        if data:
            logger.info("Skill published to ClawHub", name=name, skill_id=data.get("skill_id"))
        return data

    async def fetch_marketplace_skills(
        self,
        query: str = "",
        language: str = "",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Fetch available skills from the ClawHub marketplace.

        Args:
            query: Search query (keyword match on name/description).
            language: Filter by language.
            limit: Max results.

        Returns:
            List of skill metadata dicts.
        """
        if not self._connected or not self._session:
            return []

        params = f"?limit={limit}"
        if query:
            from urllib.parse import quote
            params += f"&q={quote(query)}"
        if language:
            params += f"&language={language}"

        url = urljoin(self._base_url, f"/api/v1/marketplace/skills{params}")
        data = await self._request("GET", url)
        if not data or "skills" not in data:
            return []

        skills = data["skills"]
        logger.info("Marketplace skills fetched", count=len(skills), query=query)
        return skills

    async def sync_skills_with_library(
        self,
        skill_library: Any,
    ) -> Dict[str, int]:
        """Synchronize local SkillLibrary with ClawHub marketplace.

        1. Publishes local skills that are not on the marketplace.
        2. Downloads marketplace skills not in local library.

        Returns:
            {"published": N, "downloaded": N}
        """
        stats = {"published": 0, "downloaded": 0}

        if not self._connected:
            return stats

        # 1. Publish local skills
        local_skills = skill_library.list_skills()
        for skill_info in local_skills:
            sid = skill_info.get("skill_id", "")
            local_skill = skill_library.find_skill(skill_info.get("name", ""))
            if local_skill and local_skill.success_count >= 1:
                result = await self.publish_skill(
                    name=local_skill.name,
                    description=local_skill.description,
                    code=local_skill.code if hasattr(local_skill, "code") else "",
                    language=local_skill.language,
                    tags=["auto-published", "sandbox-tested"],
                )
                if result:
                    stats["published"] += 1

        # 2. Download marketplace skills
        remote_skills = await self.fetch_marketplace_skills(limit=50)
        local_names = {s.get("name", "").lower() for s in local_skills}

        for remote in remote_skills:
            remote_name = remote.get("name", "")
            if remote_name.lower() not in local_names:
                code = remote.get("code", "")
                if code:
                    skill_library.save_skill(
                        name=remote_name,
                        description=remote.get("description", ""),
                        code=code,
                        language=remote.get("language", "python"),
                    )
                    stats["downloaded"] += 1

        logger.info("Skill sync completed", **stats)
        return stats
