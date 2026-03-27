"""
GitHub parser — fetches trending repos and search results via GitHub REST API.

Uses GitHub's public API (no token required for read-only, 60 req/hr).
If GITHUB_TOKEN env var is set, authenticated requests get 5000 req/hr.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

logger = structlog.get_logger("parsers.github")

_GITHUB_API = "https://api.github.com"
_REQUEST_TIMEOUT = 20


@dataclass
class GitHubRepo:
    """Parsed GitHub repository."""
    name: str
    full_name: str
    url: str
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    topics: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    license: str = ""


async def fetch_github_trending(
    query: str = "language:python stars:>100",
    sort: str = "stars",
    order: str = "desc",
    limit: int = 15,
    timeout: int = _REQUEST_TIMEOUT,
) -> List[GitHubRepo]:
    """Search GitHub repos by query (trending = sorted by stars/updated).

    Args:
        query: GitHub search query (e.g. "topic:llm language:python").
        sort: Sort field — "stars", "forks", "updated", "help-wanted-issues".
        order: "desc" or "asc".
        limit: Maximum repos to return (max 100).
        timeout: Request timeout in seconds.

    Returns:
        List of GitHubRepo objects.
    """
    limit = min(limit, 100)
    url = f"{_GITHUB_API}/search/repositories?q={query}&sort={sort}&order={order}&per_page={limit}"

    headers = _build_headers()

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=headers,
        ) as session:
            async with session.get(url) as resp:
                if resp.status == 403:
                    logger.warning("GitHub API rate-limited")
                    return []
                if resp.status != 200:
                    logger.warning("GitHub search failed", status=resp.status)
                    return []
                data = await resp.json()
    except Exception as e:
        logger.warning("GitHub fetch error", error=str(e))
        return []

    return _parse_search_results(data, limit)


async def fetch_github_repo_readme(
    owner: str,
    repo: str,
    timeout: int = _REQUEST_TIMEOUT,
) -> str:
    """Fetch the raw README content of a GitHub repo.

    Returns:
        README text content, or empty string on failure.
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/readme"
    headers = _build_headers()
    headers["Accept"] = "application/vnd.github.raw+json"

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=headers,
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return ""
                return await resp.text()
    except Exception:
        return ""


async def fetch_github_releases(
    owner: str,
    repo: str,
    limit: int = 5,
    timeout: int = _REQUEST_TIMEOUT,
) -> List[Dict[str, Any]]:
    """Fetch recent releases of a GitHub repo.

    Returns:
        List of dicts with keys: tag_name, name, body, published_at, html_url.
    """
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/releases?per_page={limit}"
    headers = _build_headers()

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=headers,
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
    except Exception:
        return []

    return [
        {
            "tag_name": r.get("tag_name", ""),
            "name": r.get("name", ""),
            "body": (r.get("body", "") or "")[:1000],
            "published_at": r.get("published_at", ""),
            "html_url": r.get("html_url", ""),
        }
        for r in data[:limit]
    ]


def _build_headers() -> Dict[str, str]:
    """Build request headers, including auth token if available."""
    headers: Dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "OpenClawBot/1.0",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_search_results(data: dict, limit: int) -> List[GitHubRepo]:
    """Parse GitHub search API response."""
    repos: List[GitHubRepo] = []
    items = data.get("items", [])

    for item in items[:limit]:
        license_info = item.get("license") or {}
        repos.append(GitHubRepo(
            name=item.get("name", ""),
            full_name=item.get("full_name", ""),
            url=item.get("html_url", ""),
            description=item.get("description", "") or "",
            language=item.get("language", "") or "",
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
            open_issues=item.get("open_issues_count", 0),
            topics=item.get("topics", []),
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            license=license_info.get("spdx_id", ""),
        ))

    logger.info("GitHub repos parsed", count=len(repos))
    return repos
