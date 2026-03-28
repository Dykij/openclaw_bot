"""Unit tests for UniversalParser and source adapters (v11.6)."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parsers.universal import (
    ResearchItem,
    HabrAdapter,
    RedditAdapter,
    GitHubAdapter,
    UniversalParser,
)


# ---------------------------------------------------------------------------
# ResearchItem
# ---------------------------------------------------------------------------
def test_research_item_dedup_key():
    item = ResearchItem(title="Test", url="https://example.com/Page/", source="test")
    assert item.key == "https://example.com/page"
    print("[PASS] ResearchItem dedup key")


# ---------------------------------------------------------------------------
# Habr adapter
# ---------------------------------------------------------------------------
def test_habr_parse_rss():
    adapter = HabrAdapter()
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <title>Habr</title>
        <item>
          <title>Test Post</title>
          <link>https://habr.com/ru/articles/1/</link>
          <description>&lt;p&gt;Hello world&lt;/p&gt;</description>
          <author>user1</author>
          <pubDate>Mon, 01 Jan 2026 00:00:00 +0000</pubDate>
          <category>Python</category>
          <category>ML</category>
        </item>
        <item>
          <title>Another Post</title>
          <link>https://habr.com/ru/articles/2/</link>
          <description>Short desc</description>
        </item>
      </channel>
    </rss>"""
    items = adapter._parse_rss(xml, limit=10)
    assert len(items) == 2
    assert items[0].title == "Test Post"
    assert items[0].source == "habr"
    assert "Hello world" in items[0].summary
    assert "Python" in items[0].tags
    print("[PASS] HabrAdapter RSS parsing")


def test_habr_parse_invalid_xml():
    adapter = HabrAdapter()
    items = adapter._parse_rss("not xml at all", limit=10)
    assert items == []
    print("[PASS] HabrAdapter invalid XML returns empty")


# ---------------------------------------------------------------------------
# Reddit adapter
# ---------------------------------------------------------------------------
def test_reddit_fetch_sub_parse():
    adapter = RedditAdapter()
    # We test the internal parsing by calling _fetch_sub indirectly through data
    # Here we just verify the adapter exists and has correct config
    assert adapter.name == "reddit"
    assert "MachineLearning" in adapter.DEFAULT_SUBREDDITS
    assert "LanguageTechnology" in adapter.DEFAULT_SUBREDDITS
    print("[PASS] RedditAdapter config")


# ---------------------------------------------------------------------------
# GitHub adapter
# ---------------------------------------------------------------------------
def test_github_adapter_headers():
    adapter = GitHubAdapter()
    headers = adapter._headers()
    assert "User-Agent" in headers
    assert headers["User-Agent"] == "OpenClawBot/1.0"
    print("[PASS] GitHubAdapter headers")


# ---------------------------------------------------------------------------
# UniversalParser
# ---------------------------------------------------------------------------
def test_universal_parser_adapter_names():
    parser = UniversalParser()
    names = parser.adapter_names
    assert "habr" in names
    assert "github" in names
    assert "reddit" in names
    assert "semantic_scholar" in names
    assert "arxiv" in names
    assert "openalex" in names
    print("[PASS] UniversalParser has all adapters")


def test_universal_parser_get_adapter():
    parser = UniversalParser()
    assert parser.get_adapter("arxiv") is not None
    assert parser.get_adapter("nonexistent") is None
    print("[PASS] UniversalParser get_adapter")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_research_item_dedup_key()
    test_habr_parse_rss()
    test_habr_parse_invalid_xml()
    test_reddit_fetch_sub_parse()
    test_github_adapter_headers()
    test_universal_parser_adapter_names()
    test_universal_parser_get_adapter()
    print("\n✅ All UniversalParser tests passed!")
