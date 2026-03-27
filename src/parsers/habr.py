"""
Habr.com parser — fetches articles from Habr RSS feed by topic.

Uses Habr's public RSS/Atom feeds (no API key required).
Supports tag-based and search-based article discovery.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from typing import List, Optional

import aiohttp
import structlog

logger = structlog.get_logger("parsers.habr")

_HABR_RSS_BASE = "https://habr.com/ru/rss/articles/"
_HABR_SEARCH_RSS = "https://habr.com/ru/rss/search/?q={query}&target_type=posts"
_REQUEST_TIMEOUT = 20


@dataclass
class HabrArticle:
    """Parsed Habr article."""
    title: str
    url: str
    author: str = ""
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    published: str = ""
    score: int = 0


async def fetch_habr_articles(
    query: str = "",
    limit: int = 15,
    timeout: int = _REQUEST_TIMEOUT,
) -> List[HabrArticle]:
    """Fetch articles from Habr by search query or recent feed.

    Args:
        query: Search query. If empty, fetches recent articles.
        limit: Maximum number of articles to return.
        timeout: Request timeout in seconds.

    Returns:
        List of HabrArticle objects.
    """
    url = _HABR_SEARCH_RSS.format(query=query) if query else _HABR_RSS_BASE

    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    logger.warning("Habr RSS failed", status=resp.status)
                    return []
                xml_text = await resp.text()
    except Exception as e:
        logger.warning("Habr fetch error", error=str(e))
        return []

    return _parse_rss_xml(xml_text, limit)


def _parse_rss_xml(xml_text: str, limit: int) -> List[HabrArticle]:
    """Parse RSS XML into HabrArticle list."""
    import xml.etree.ElementTree as ET

    articles: List[HabrArticle] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.warning("Habr XML parse error", error=str(e))
        return []

    # RSS 2.0: channel/item
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")

    for item in items[:limit]:
        title = _text(item, "title")
        link = _text(item, "link")
        if not title or not link:
            continue

        description = _text(item, "description")
        # Strip HTML tags from description
        summary = re.sub(r"<[^>]+>", "", description)[:500] if description else ""

        author = _text(item, "author") or _text(item, "{http://purl.org/dc/elements/1.1/}creator")
        pub_date = _text(item, "pubDate")

        # Collect category tags
        tags = [cat.text for cat in item.findall("category") if cat.text]

        articles.append(HabrArticle(
            title=title,
            url=link,
            author=author,
            summary=summary,
            tags=tags,
            published=pub_date,
        ))

    logger.info("Habr articles parsed", count=len(articles))
    return articles


def _text(element, tag: str) -> str:
    """Safely extract text from XML element."""
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""
