"""
test_fetch.py — Tests for the RSS/web fetcher

Tests the fetcher logic with mocked RSS feeds and network calls.
"""

import json
import sys
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from fetch_sources import (
    contains_keywords,
    deduplicate,
    is_recent,
    parse_date,
    save_article,
    url_hash,
)


class TestParseDate:
    def test_iso_date_string(self):
        dt = parse_date("2025-03-15T09:00:00+00:00")
        assert dt is not None
        assert dt.year == 2025
        assert dt.month == 3
        assert dt.day == 15

    def test_rss_style_date(self):
        dt = parse_date("Thu, 15 Mar 2025 09:00:00 GMT")
        assert dt is not None
        assert dt.year == 2025

    def test_naive_datetime_gets_utc(self):
        dt = parse_date("2025-03-15T09:00:00")
        assert dt is not None
        assert dt.tzinfo is not None

    def test_none_returns_none(self):
        dt = parse_date(None)
        assert dt is None

    def test_garbage_string_returns_none(self):
        dt = parse_date("not a date at all !!!")
        assert dt is None

    def test_returns_timezone_aware(self):
        dt = parse_date("2025-03-15T09:00:00Z")
        assert dt is not None
        assert dt.tzinfo is not None


class TestIsRecent:
    def test_recent_article_passes(self):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(hours=6)
        assert is_recent(recent, hours=24) is True

    def test_old_article_fails(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=48)
        assert is_recent(old, hours=24) is False

    def test_exactly_at_boundary(self):
        now = datetime.now(timezone.utc)
        # 24 hours ago minus 1 minute = just outside
        boundary = now - timedelta(hours=24, minutes=1)
        assert is_recent(boundary, hours=24) is False

    def test_none_date_is_included(self):
        """If we can't parse the date, conservatively include the article."""
        assert is_recent(None, hours=24) is True

    def test_custom_hours_window(self):
        now = datetime.now(timezone.utc)
        # 2 hours ago
        two_hours_ago = now - timedelta(hours=2)
        assert is_recent(two_hours_ago, hours=1) is False
        assert is_recent(two_hours_ago, hours=3) is True


class TestContainsKeywords:
    def test_keyword_found(self):
        assert contains_keywords("New tariff on steel imports", ["tariff"]) is True

    def test_keyword_case_insensitive(self):
        assert contains_keywords("New TARIFF on Steel", ["tariff"]) is True
        assert contains_keywords("new tariff", ["TARIFF"]) is True

    def test_keyword_not_found(self):
        assert contains_keywords("Weather forecast for tomorrow", ["tariff"]) is False

    def test_multiple_keywords_any_match(self):
        assert contains_keywords("Section 301 investigation opened", ["tariff", "section 301"]) is True

    def test_empty_keywords_returns_false(self):
        """Empty keyword list = no match."""
        assert contains_keywords("Any text here", []) is False

    def test_partial_word_match(self):
        """'tariff' should match 'tariffs' (substring match)."""
        assert contains_keywords("New tariffs announced", ["tariff"]) is True


class TestUrlHash:
    def test_returns_string(self):
        h = url_hash("https://example.com/article")
        assert isinstance(h, str)

    def test_returns_16_chars(self):
        h = url_hash("https://example.com/article")
        assert len(h) == 16

    def test_same_url_same_hash(self):
        url = "https://ustr.gov/press-release/12345"
        assert url_hash(url) == url_hash(url)

    def test_different_urls_different_hashes(self):
        h1 = url_hash("https://ustr.gov/press-release/1")
        h2 = url_hash("https://ustr.gov/press-release/2")
        assert h1 != h2

    def test_hexadecimal_characters(self):
        h = url_hash("https://example.com")
        assert all(c in "0123456789abcdef" for c in h)


class TestDeduplicate:
    def test_removes_duplicate_urls(self):
        articles = [
            {"url": "https://example.com/1", "title": "Article 1"},
            {"url": "https://example.com/1", "title": "Article 1 duplicate"},
            {"url": "https://example.com/2", "title": "Article 2"},
        ]
        result = deduplicate(articles)
        assert len(result) == 2
        urls = [a["url"] for a in result]
        assert "https://example.com/1" in urls
        assert "https://example.com/2" in urls

    def test_preserves_first_occurrence(self):
        articles = [
            {"url": "https://example.com/1", "title": "First"},
            {"url": "https://example.com/1", "title": "Second"},
        ]
        result = deduplicate(articles)
        assert result[0]["title"] == "First"

    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_no_duplicates_unchanged(self):
        articles = [
            {"url": "https://example.com/1"},
            {"url": "https://example.com/2"},
        ]
        result = deduplicate(articles)
        assert len(result) == 2

    def test_articles_without_url_skipped(self):
        """Articles with no URL are skipped entirely (URL required for dedup key)."""
        articles = [
            {"title": "No URL 1"},
            {"title": "No URL 2"},
        ]
        # Both have no/empty url, so the dedup key is '' — they are skipped
        result = deduplicate(articles)
        assert len(result) == 0


class TestSaveArticle:
    def test_saves_to_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            article = {
                "url": "https://ustr.gov/test",
                "title": "Test Article",
                "content": "Test content",
                "published_date": "2025-03-15T09:00:00+00:00",
                "source_name": "USTR",
                "source_category": "official_us_gov",
            }
            filename = save_article(article, output_dir)
            assert (output_dir / filename).exists()

    def test_filename_is_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            article = {"url": "https://example.com/article", "title": "Test"}
            filename = save_article(article, output_dir)
            assert filename.endswith(".json")

    def test_saved_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            article = {
                "url": "https://example.com/article-x",
                "title": "Test Article X",
                "content": "Some content",
            }
            filename = save_article(article, output_dir)
            filepath = output_dir / filename
            with open(filepath) as f:
                loaded = json.load(f)
            assert loaded["url"] == article["url"]
            assert loaded["title"] == article["title"]

    def test_same_url_same_filename(self):
        """Two saves of the same URL should produce the same filename."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            article = {"url": "https://example.com/stable", "title": "A"}
            f1 = save_article(article, output_dir)
            f2 = save_article(article, output_dir)
            assert f1 == f2


class TestFetchRssIntegration:
    """Tests for fetch_rss using mocked feedparser."""

    def _make_source(self):
        return {
            "name": "Test Source",
            "url": "https://example.com",
            "rss_url": "https://example.com/rss",
            "category": "news_wire",
            "reliability_floor": 1,
            "fetch_method": "rss",
            "keywords": ["tariff", "duty"],
        }

    def _make_feed_entry(self, hours_ago=1):
        published = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "link": "https://example.com/article-1",
            "title": "New tariff on steel imports announced",
            "summary": "The government announced new tariffs on steel.",
            "published": published.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "content": [],
        }

    def _make_feed_mock(self, entries):
        """Create a feedparser-style mock object with .entries as a list attribute."""
        class FakeFeed:
            bozo = False
            bozo_exception = None
        feed = FakeFeed()
        feed.entries = entries
        return feed

    @patch("fetch_sources.feedparser.parse")
    def test_recent_matching_article_returned(self, mock_parse):
        entry = self._make_feed_entry(hours_ago=2)
        mock_parse.return_value = self._make_feed_mock([entry])

        from fetch_sources import fetch_rss
        articles = fetch_rss(self._make_source(), hours=24)
        assert len(articles) == 1
        assert articles[0]["title"] == entry["title"]

    @patch("fetch_sources.feedparser.parse")
    def test_old_article_excluded(self, mock_parse):
        entry = self._make_feed_entry(hours_ago=30)  # 30 hours ago
        mock_parse.return_value = self._make_feed_mock([entry])

        from fetch_sources import fetch_rss
        articles = fetch_rss(self._make_source(), hours=24)
        assert len(articles) == 0

    @patch("fetch_sources.feedparser.parse")
    def test_non_matching_keyword_excluded(self, mock_parse):
        entry = {
            "link": "https://example.com/article-2",
            "title": "Sports news: soccer match results",
            "summary": "Soccer results from last night.",
            "published": datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "content": [],
        }
        mock_parse.return_value = self._make_feed_mock([entry])

        from fetch_sources import fetch_rss
        articles = fetch_rss(self._make_source(), hours=24)
        assert len(articles) == 0

    @patch("fetch_sources.feedparser.parse", side_effect=Exception("Network error"))
    def test_fetch_error_returns_empty_list(self, mock_parse):
        from fetch_sources import fetch_rss
        articles = fetch_rss(self._make_source(), hours=24)
        assert articles == []

    @patch("fetch_sources.feedparser.parse")
    def test_article_has_required_fields(self, mock_parse):
        entry = self._make_feed_entry(hours_ago=1)
        mock_parse.return_value = self._make_feed_mock([entry])

        from fetch_sources import fetch_rss
        articles = fetch_rss(self._make_source(), hours=24)
        assert len(articles) == 1
        article = articles[0]

        required_fields = [
            "url", "title", "content", "published_date",
            "source_name", "source_category", "source_url",
            "reliability_floor", "fetched_at",
        ]
        for field in required_fields:
            assert field in article, f"Missing field: {field}"
