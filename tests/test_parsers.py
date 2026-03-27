"""Unit tests for multi-source parsers (Habr, Reddit, GitHub)."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parsers.habr import HabrArticle, _parse_rss_xml
from src.parsers.reddit import RedditPost, _parse_listing
from src.parsers.github import GitHubRepo, _parse_search_results


# ---------------------------------------------------------------------------
# Habr parser
# ---------------------------------------------------------------------------
def test_habr_article_dataclass():
    article = HabrArticle(
        title="Test Article",
        url="https://habr.com/ru/articles/123/",
        author="test_user",
        summary="A test article",
        tags=["python", "ml"],
    )
    assert article.title == "Test Article"
    assert len(article.tags) == 2
    print("[PASS] HabrArticle dataclass")


def test_habr_parse_rss_xml():
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
    articles = _parse_rss_xml(xml, limit=10)
    assert len(articles) == 2
    assert articles[0].title == "Test Post"
    assert "Hello world" in articles[0].summary  # HTML stripped
    assert "Python" in articles[0].tags
    assert articles[1].title == "Another Post"
    print("[PASS] habr RSS XML parsing")


def test_habr_parse_invalid_xml():
    articles = _parse_rss_xml("not xml at all", limit=10)
    assert articles == []
    print("[PASS] habr invalid XML returns empty")


# ---------------------------------------------------------------------------
# Reddit parser
# ---------------------------------------------------------------------------
def test_reddit_post_dataclass():
    post = RedditPost(
        title="Test Post",
        url="https://reddit.com/r/test/1",
        subreddit="test",
        score=42,
    )
    assert post.title == "Test Post"
    assert post.score == 42
    assert post.num_comments == 0
    print("[PASS] RedditPost dataclass")


def test_reddit_parse_listing():
    data = {
        "data": {
            "children": [
                {
                    "data": {
                        "title": "First Post",
                        "permalink": "/r/test/comments/abc/first_post/",
                        "subreddit": "test",
                        "author": "user1",
                        "selftext": "Hello from Reddit",
                        "score": 100,
                        "num_comments": 5,
                        "created_utc": 1700000000.0,
                        "link_flair_text": "Discussion",
                    }
                },
                {
                    "data": {
                        "title": "Second Post",
                        "permalink": "/r/test/comments/def/second/",
                        "subreddit": "test",
                        "author": "user2",
                        "selftext": "",
                        "score": 50,
                        "num_comments": 2,
                    }
                },
            ]
        }
    }
    posts = _parse_listing(data, limit=10)
    assert len(posts) == 2
    assert posts[0].title == "First Post"
    assert posts[0].score == 100
    assert posts[0].flair == "Discussion"
    assert posts[1].selftext == ""
    print("[PASS] reddit listing parsing")


def test_reddit_parse_empty_listing():
    data = {"data": {"children": []}}
    posts = _parse_listing(data, limit=10)
    assert posts == []
    print("[PASS] reddit empty listing")


# ---------------------------------------------------------------------------
# GitHub parser
# ---------------------------------------------------------------------------
def test_github_repo_dataclass():
    repo = GitHubRepo(
        name="test-repo",
        full_name="user/test-repo",
        url="https://github.com/user/test-repo",
        stars=500,
        language="Python",
    )
    assert repo.name == "test-repo"
    assert repo.stars == 500
    assert repo.topics == []
    print("[PASS] GitHubRepo dataclass")


def test_github_parse_search_results():
    data = {
        "items": [
            {
                "name": "cool-project",
                "full_name": "org/cool-project",
                "html_url": "https://github.com/org/cool-project",
                "description": "A cool ML project",
                "language": "Python",
                "stargazers_count": 1200,
                "forks_count": 120,
                "open_issues_count": 15,
                "topics": ["machine-learning", "python"],
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2026-03-25T00:00:00Z",
                "license": {"spdx_id": "MIT"},
            },
            {
                "name": "another-repo",
                "full_name": "user/another-repo",
                "html_url": "https://github.com/user/another-repo",
                "description": None,
                "language": None,
                "stargazers_count": 50,
                "forks_count": 5,
                "open_issues_count": 0,
                "topics": [],
                "license": None,
            },
        ]
    }
    repos = _parse_search_results(data, limit=10)
    assert len(repos) == 2
    assert repos[0].name == "cool-project"
    assert repos[0].stars == 1200
    assert repos[0].license == "MIT"
    assert repos[0].topics == ["machine-learning", "python"]
    assert repos[1].description == ""  # None → ""
    assert repos[1].license == ""
    print("[PASS] github search results parsing")


def test_github_parse_empty_results():
    data = {"items": []}
    repos = _parse_search_results(data, limit=10)
    assert repos == []
    print("[PASS] github empty search results")


# ---------------------------------------------------------------------------
# Run all
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_habr_article_dataclass()
    test_habr_parse_rss_xml()
    test_habr_parse_invalid_xml()
    test_reddit_post_dataclass()
    test_reddit_parse_listing()
    test_reddit_parse_empty_listing()
    test_github_repo_dataclass()
    test_github_parse_search_results()
    test_github_parse_empty_results()
    print("\n✅ All parser tests passed!")
