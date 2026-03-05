#!/usr/bin/env python3
"""
fetch_sources.py — Tariff source fetcher

Reads config/sources.yaml, fetches each RSS feed or scrapes each web source,
filters for content published in the last 24 hours, deduplicates by URL,
and saves raw articles to data/raw/YYYY-MM-DD/ as JSON files.

Usage:
    python scripts/fetch_sources.py [--date YYYY-MM-DD] [--hours N]
"""

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser

# ── Logging setup ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("fetch_sources")

# ── Constants ─────────────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "sources.yaml"
DATA_RAW = REPO_ROOT / "data" / "raw"

REQUEST_TIMEOUT = 30  # seconds
INTER_SOURCE_DELAY = 1.0  # seconds between sources
SCRAPE_DELAY = 2.0  # seconds between scrape requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CavelaTariffTracker/1.0; "
        "+https://github.com/asardain/cavela-tariff-tracker)"
    )
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def load_sources() -> list[dict]:
    """Load and return active sources from sources.yaml."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    sources = [s for s in config.get("sources", []) if s.get("active", True)]
    logger.info(f"Loaded {len(sources)} active sources")
    return sources


def url_hash(url: str) -> str:
    """Return a short hash of a URL for use as a filename."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse a date string into a timezone-aware datetime, or None on failure."""
    if not date_str:
        return None
    try:
        dt = dateutil_parser.parse(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def is_recent(dt: Optional[datetime], hours: int) -> bool:
    """Return True if dt is within the last `hours` hours."""
    if dt is None:
        # If we can't parse the date, include it (conservative)
        return True
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return dt >= cutoff


def contains_keywords(text: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in text (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def save_article(article: dict, output_dir: Path) -> str:
    """Save an article dict to output_dir. Returns the saved filename."""
    article_hash = url_hash(article["url"])
    filename = f"{article_hash}.json"
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(article, f, indent=2, default=str)
    return filename


# ── Fetchers ──────────────────────────────────────────────────────────────────


def fetch_rss(source: dict, hours: int) -> list[dict]:
    """
    Fetch and parse an RSS feed for the given source.
    Returns list of article dicts that match keywords and are within `hours`.
    """
    rss_url = source.get("rss_url")
    if not rss_url:
        logger.warning(f"[{source['name']}] No RSS URL configured")
        return []

    logger.info(f"[{source['name']}] Fetching RSS: {rss_url}")

    try:
        # feedparser handles redirects, SSL, gzip natively
        feed = feedparser.parse(
            rss_url,
            request_headers=HEADERS,
            agent=HEADERS["User-Agent"],
        )
    except Exception as e:
        logger.warning(f"[{source['name']}] RSS fetch failed: {e}")
        return []

    if feed.bozo and feed.bozo_exception:
        # bozo = malformed feed; log but continue if entries present
        logger.warning(
            f"[{source['name']}] Malformed RSS: {feed.bozo_exception}"
        )

    entries = getattr(feed, "entries", []) or []
    logger.info(f"[{source['name']}] Got {len(entries)} RSS entries")

    articles = []
    keywords = source.get("keywords", [])

    for entry in entries:
        url = entry.get("link", "")
        if not url:
            continue

        title = entry.get("title", "")
        summary = entry.get("summary", "") or entry.get("description", "")
        content_list = entry.get("content", [])
        content_text = content_list[0].get("value", "") if content_list else ""
        full_text = f"{title} {summary} {content_text}"

        # Filter by keywords
        if keywords and not contains_keywords(full_text, keywords):
            continue

        # Parse published date
        published_str = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("created")
        )
        published_dt = parse_date(published_str)

        # Filter by recency
        if not is_recent(published_dt, hours):
            continue

        article = {
            "url": url,
            "title": title,
            "content": (summary or content_text)[:5000],  # cap at 5000 chars
            "published_date": published_dt.isoformat() if published_dt else None,
            "source_name": source["name"],
            "source_category": source["category"],
            "source_url": source["url"],
            "reliability_floor": source.get("reliability_floor", 1),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        articles.append(article)

    logger.info(
        f"[{source['name']}] {len(articles)} articles matched keywords + recency"
    )
    return articles


def fetch_scrape(source: dict, hours: int) -> list[dict]:
    """
    Scrape a web page to find article links, then fetch each article.
    Returns list of article dicts.
    """
    url = source.get("url")
    selector = source.get("scrape_selector", "a[href]")
    keywords = source.get("keywords", [])

    logger.info(f"[{source['name']}] Scraping: {url}")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"[{source['name']}] Scrape failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    links = []
    for tag in soup.select(selector):
        href = tag.get("href", "")
        if not href:
            continue
        if href.startswith("/"):
            href = base + href
        elif not href.startswith("http"):
            continue
        text = tag.get_text(strip=True)
        if keywords and not contains_keywords(text, keywords):
            continue
        links.append((href, text))

    logger.info(f"[{source['name']}] Found {len(links)} candidate links")

    articles = []
    for href, link_text in links[:20]:  # cap at 20 links per source
        time.sleep(SCRAPE_DELAY)
        try:
            art_resp = requests.get(href, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            art_resp.raise_for_status()
            art_soup = BeautifulSoup(art_resp.text, "lxml")

            # Try to extract article content
            content = ""
            for tag in ["article", "main", ".article-body", ".entry-content"]:
                el = art_soup.select_one(tag)
                if el:
                    content = el.get_text(separator=" ", strip=True)[:5000]
                    break
            if not content:
                content = art_soup.get_text(separator=" ", strip=True)[:3000]

            full_text = f"{link_text} {content}"
            if keywords and not contains_keywords(full_text, keywords):
                continue

            article = {
                "url": href,
                "title": link_text,
                "content": content,
                "published_date": None,  # hard to determine from scrape
                "source_name": source["name"],
                "source_category": source["category"],
                "source_url": source["url"],
                "reliability_floor": source.get("reliability_floor", 1),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            articles.append(article)

        except requests.RequestException as e:
            logger.warning(f"[{source['name']}] Failed to fetch {href}: {e}")
            continue

    return articles


# ── Deduplication ─────────────────────────────────────────────────────────────


def deduplicate(articles: list[dict]) -> list[dict]:
    """Deduplicate articles by URL. Keep the first occurrence."""
    seen_urls = set()
    unique = []
    for article in articles:
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique.append(article)
    return unique


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch tariff sources")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="Output date (YYYY-MM-DD), defaults to today UTC",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only include articles published in last N hours (default: 24)",
    )
    args = parser.parse_args()

    output_dir = DATA_RAW / args.date
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Output directory: {output_dir}")

    sources = load_sources()
    all_articles: list[dict] = []

    for source in sources:
        try:
            method = source.get("fetch_method", "rss")
            if method == "rss":
                articles = fetch_rss(source, args.hours)
            elif method == "scrape":
                articles = fetch_scrape(source, args.hours)
            else:
                logger.warning(f"[{source['name']}] Unknown fetch_method: {method}")
                articles = []

            all_articles.extend(articles)

        except Exception as e:
            logger.error(
                f"[{source['name']}] Unexpected error: {e}", exc_info=True
            )
            # Continue to next source — never crash the pipeline

        time.sleep(INTER_SOURCE_DELAY)

    # Deduplicate across all sources
    unique_articles = deduplicate(all_articles)
    logger.info(
        f"Total: {len(all_articles)} articles fetched, "
        f"{len(unique_articles)} after deduplication"
    )

    # Save each article
    saved = 0
    for article in unique_articles:
        try:
            filename = save_article(article, output_dir)
            logger.debug(f"Saved: {filename}")
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to save article {article.get('url')}: {e}")

    logger.info(f"Saved {saved} articles to {output_dir}")

    # Write a manifest file
    manifest = {
        "date": args.date,
        "hours_window": args.hours,
        "sources_attempted": len(sources),
        "articles_fetched": len(all_articles),
        "articles_saved": saved,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"Manifest written to {manifest_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
