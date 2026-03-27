"""
Reddit parser — fetches posts from subreddits via public JSON API.

Uses Reddit's public `.json` endpoint (no OAuth, no API key).
Rate-limited to respect Reddit's terms (1 req/2 sec).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import List, Optional

import aiohttp
import structlog

logger = structlog.get_logger("parsers.reddit")

_REDDIT_BASE = "https://www.reddit.com"
_USER_AGENT = "OpenClawBot/1.0 (research parser)"
_REQUEST_TIMEOUT = 20

# Default subreddits for AI/ML/trading research
DEFAULT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "artificial",
    "algotrading",
    "MLOps",
]


@dataclass
class RedditPost:
    """Parsed Reddit post."""
    title: str
    url: str
    subreddit: str
    author: str = ""
    selftext: str = ""
    score: int = 0
    num_comments: int = 0
    created_utc: float = 0.0
    permalink: str = ""
    flair: str = ""


async def fetch_reddit_posts(
    subreddit: str = "MachineLearning",
    sort: str = "hot",
    limit: int = 15,
    query: str = "",
    timeout: int = _REQUEST_TIMEOUT,
) -> List[RedditPost]:
    """Fetch posts from a subreddit.

    Args:
        subreddit: Subreddit name (without r/).
        sort: Sort method — "hot", "new", "top", "rising".
        limit: Maximum posts to return (max 100).
        query: If set, search within subreddit instead of browsing.
        timeout: Request timeout in seconds.

    Returns:
        List of RedditPost objects.
    """
    limit = min(limit, 100)

    if query:
        url = f"{_REDDIT_BASE}/r/{subreddit}/search.json?q={query}&restrict_sr=1&sort=relevance&limit={limit}"
    else:
        url = f"{_REDDIT_BASE}/r/{subreddit}/{sort}.json?limit={limit}"

    headers = {"User-Agent": _USER_AGENT}

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers=headers,
        ) as session:
            async with session.get(url) as resp:
                if resp.status == 429:
                    logger.warning("Reddit rate-limited, waiting 3s")
                    await asyncio.sleep(3)
                    return []
                if resp.status != 200:
                    logger.warning("Reddit fetch failed", status=resp.status, subreddit=subreddit)
                    return []
                data = await resp.json()
    except Exception as e:
        logger.warning("Reddit fetch error", error=str(e))
        return []

    return _parse_listing(data, limit)


async def fetch_reddit_multi(
    subreddits: Optional[List[str]] = None,
    sort: str = "hot",
    limit_per_sub: int = 10,
) -> List[RedditPost]:
    """Fetch posts from multiple subreddits concurrently.

    Args:
        subreddits: List of subreddit names. Defaults to DEFAULT_SUBREDDITS.
        sort: Sort method.
        limit_per_sub: Max posts per subreddit.

    Returns:
        Combined list of posts, sorted by score descending.
    """
    subs = subreddits or DEFAULT_SUBREDDITS
    tasks = []
    for sub in subs:
        tasks.append(fetch_reddit_posts(subreddit=sub, sort=sort, limit=limit_per_sub))
        # Small delay between requests to respect rate limits
        await asyncio.sleep(0.5)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    posts: List[RedditPost] = []
    for result in results:
        if isinstance(result, list):
            posts.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Reddit multi-fetch error", error=str(result))

    posts.sort(key=lambda p: p.score, reverse=True)
    return posts


def _parse_listing(data: dict, limit: int) -> List[RedditPost]:
    """Parse Reddit listing JSON into RedditPost list."""
    posts: List[RedditPost] = []

    children = data.get("data", {}).get("children", [])
    for child in children[:limit]:
        d = child.get("data", {})
        if not d.get("title"):
            continue

        permalink = d.get("permalink", "")
        full_url = f"{_REDDIT_BASE}{permalink}" if permalink else d.get("url", "")

        posts.append(RedditPost(
            title=d.get("title", ""),
            url=full_url,
            subreddit=d.get("subreddit", ""),
            author=d.get("author", ""),
            selftext=d.get("selftext", "")[:1000],  # Trim long posts
            score=d.get("score", 0),
            num_comments=d.get("num_comments", 0),
            created_utc=d.get("created_utc", 0.0),
            permalink=permalink,
            flair=d.get("link_flair_text", "") or "",
        ))

    logger.info("Reddit posts parsed", count=len(posts))
    return posts
