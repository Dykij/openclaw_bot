"""
Parsers package — Multi-source data parsers for OpenClaw Bot.

Each parser provides async `fetch_*` functions that return structured data
for ingestion by SuperMemory/RAG and Deep Research pipelines.
"""

from src.parsers.habr import fetch_habr_articles, HabrArticle
from src.parsers.reddit import fetch_reddit_posts, RedditPost
from src.parsers.github import fetch_github_trending, GitHubRepo

__all__ = [
    "fetch_habr_articles",
    "HabrArticle",
    "fetch_reddit_posts",
    "RedditPost",
    "fetch_github_trending",
    "GitHubRepo",
]
