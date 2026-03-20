"""
rss_fetcher.py — RSS Fetching Service (MongoDB-backed)
======================================================
Refactored from the original src/rss_fetcher.py. Core fetching logic
(strategies, HTML cleaning) is preserved. Storage and deduplication
now use MongoDB instead of JSONL + SQLite.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup
from pymongo.errors import DuplicateKeyError

from app.core.config import get_settings
from app.core.database import get_db

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("eureka.rss_fetcher")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "feeds_config.json"
HTTP_TIMEOUT = 15


# ===========================================================================
# URL Resolution
# ===========================================================================
def resolve_feed_url(raw_url: str) -> str:
    """
    Resolve a feed URL from the config.
    Relative paths (starting with /) are prefixed with RSSHUB_BASE_URL.
    Full URLs are returned as-is.
    """
    if raw_url.startswith("/"):
        base = get_settings().rsshub_base_url.rstrip("/")
        return f"{base}{raw_url}"
    return raw_url


# ===========================================================================
# Configuration Loader
# ===========================================================================
def load_feeds_config(config_path: Path = CONFIG_PATH) -> list[dict[str, Any]]:
    """Load and return only the *active* feed entries from feeds_config.json."""
    logger.info("Loading feed configuration from %s", config_path)
    with open(config_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    all_feeds = data.get("feeds", [])
    active_feeds = [f for f in all_feeds if f.get("active", False)]
    logger.info("Found %d feeds total, %d active.", len(all_feeds), len(active_feeds))
    return active_feeds


# ===========================================================================
# HTML Cleaning Utility
# ===========================================================================
def strip_html(raw_html: str | None) -> str:
    """
    Remove all HTML tags using BeautifulSoup, preserving meaningful
    whitespace and newlines.
    """
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")

    for br_tag in soup.find_all("br"):
        br_tag.replace_with("\n")
    for block_tag in soup.find_all(["p", "div", "li"]):
        block_tag.insert_before("\n")
        block_tag.insert_after("\n")

    text = soup.get_text()
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()


# ===========================================================================
# Fetch Strategies
# ===========================================================================
def fetch_full_rss(entry: feedparser.FeedParserDict) -> str:
    """FULL_RSS — extract content from RSS description and strip HTML."""
    content_blocks = entry.get("content", [])
    if content_blocks:
        raw = content_blocks[0].get("value", "")
    else:
        raw = entry.get("description", "") or entry.get("summary", "")
    return strip_html(raw)


def fetch_scrape_web(entry: feedparser.FeedParserDict) -> str:
    """SCRAPE_WEB — follow article link and extract full text via trafilatura."""
    link = entry.get("link", "")
    if not link:
        logger.warning("SCRAPE_WEB: entry has no link, falling back to RSS body.")
        return fetch_full_rss(entry)

    try:
        downloaded = trafilatura.fetch_url(link)
        if downloaded:
            text = trafilatura.extract(downloaded, favor_precision=True)
            if text:
                return text.strip()

        logger.warning("trafilatura.fetch_url returned nothing for %s, trying requests.", link)
        resp = requests.get(link, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EurekaNews/1.0)"
        })
        resp.raise_for_status()
        text = trafilatura.extract(resp.text, favor_precision=True)
        if text:
            return text.strip()

    except Exception as exc:
        logger.error("SCRAPE_WEB failed for %s: %s", link, exc, exc_info=True)

    logger.warning("Falling back to RSS description for %s", link)
    return fetch_full_rss(entry)


def fetch_summary_only(entry: feedparser.FeedParserDict) -> str:
    """SUMMARY_ONLY — concatenate title + description for paywalled sources."""
    title = entry.get("title", "").strip()
    desc = strip_html(entry.get("description", "") or entry.get("summary", ""))
    parts = [p for p in (title, desc) if p]
    return "\n\n".join(parts)


STRATEGY_MAP = {
    "FULL_RSS": fetch_full_rss,
    "SCRAPE_WEB": fetch_scrape_web,
    "SUMMARY_ONLY": fetch_summary_only,
}


# ===========================================================================
# Synchronous Feed Processing (runs in thread via asyncio.to_thread)
# ===========================================================================
def _process_feed_sync(
    feed_id: str,
    feed_url: str,
    strategy_name: str,
    category: str,
) -> list[dict[str, Any]]:
    """
    Parse a single RSS feed and build article records.
    This is synchronous because feedparser and trafilatura are sync libraries.
    Returns a list of article dicts ready for MongoDB insertion.
    """
    strategy_fn = STRATEGY_MAP.get(strategy_name)
    if strategy_fn is None:
        logger.warning("Unknown strategy '%s' for %s, falling back to FULL_RSS.", strategy_name, feed_id)
        strategy_fn = fetch_full_rss

    parsed = feedparser.parse(feed_url)

    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"feedparser could not parse {feed_url}: {parsed.bozo_exception}")

    entries = parsed.entries
    logger.info("Parsed %d entries from %s", len(entries), feed_url)

    articles = []
    for entry in entries:
        link = entry.get("link", "")
        title = entry.get("title", "(no title)")

        if not link:
            logger.warning("Skipping entry with no link: %s", title)
            continue

        try:
            content = strategy_fn(entry)
        except Exception as exc:
            logger.error("Strategy %s failed for '%s' (%s): %s", strategy_name, title, link, exc, exc_info=True)
            content = ""

        if not content:
            logger.warning("Empty content for '%s' — writing record anyway.", title)

        articles.append({
            "_id": str(uuid.uuid4()),
            "feed_id": feed_id,
            "category": category,
            "title": title,
            "link": link,
            "content": content,
            "fetch_time": datetime.now(timezone.utc),
        })

    return articles


# ===========================================================================
# Async Orchestrator
# ===========================================================================
async def run_fetch_cycle() -> dict[str, int]:
    """
    Execute one full fetch cycle: load config → iterate feeds →
    parse RSS → insert to MongoDB (skip duplicates via unique index).
    After fetching, automatically triggers LLM analysis on all
    unanalyzed articles in the database.

    Returns a summary dict: {"new": N, "skipped": M}.
    """
    logger.info("=" * 60)
    logger.info("Starting new fetch cycle at %s", datetime.now(timezone.utc).isoformat())
    logger.info("=" * 60)

    try:
        feeds = load_feeds_config()
    except Exception as exc:
        logger.error("Failed to load feed configuration: %s", exc, exc_info=True)
        return {"new": 0, "skipped": 0}

    db = get_db()
    collection = db["articles"]
    total_new = 0
    total_skipped = 0

    for feed_cfg in feeds:
        feed_id = feed_cfg["id"]
        feed_name = feed_cfg.get("name", feed_id)
        feed_url = resolve_feed_url(feed_cfg["url"])
        strategy_name = feed_cfg.get("fetch_strategy", "FULL_RSS")
        category = feed_cfg.get("category", "")

        logger.info("--- Processing feed: %s (%s) [%s] ---", feed_name, feed_id, strategy_name)

        try:
            # Run sync feed processing in a thread to avoid blocking the event loop
            articles = await asyncio.to_thread(
                _process_feed_sync,
                feed_id=feed_id,
                feed_url=feed_url,
                strategy_name=strategy_name,
                category=category,
            )

            # Insert articles into MongoDB, skipping duplicates
            new_count = 0
            skip_count = 0
            for article in articles:
                try:
                    await collection.insert_one(article)
                    new_count += 1
                except DuplicateKeyError:
                    skip_count += 1

            total_new += new_count
            total_skipped += skip_count
            logger.info("Feed %s done: %d new, %d duplicates skipped.", feed_id, new_count, skip_count)

        except Exception as exc:
            logger.error("Feed %s (%s) FAILED — skipping. Error: %s", feed_name, feed_url, exc, exc_info=True)

    logger.info("Fetch cycle complete. Total new: %d, Total skipped: %d.", total_new, total_skipped)

    # --- Auto-trigger LLM analysis on all unanalyzed articles ---
    from app.services.news_analyzer import analyze_articles

    logger.info("=" * 60)
    logger.info("Auto-triggering LLM analysis for unanalyzed articles...")
    logger.info("=" * 60)
    try:
        result = await analyze_articles()
        logger.info(
            "LLM analysis complete. Analyzed: %d, Failed: %d, Skipped: %d.",
            result["analyzed"], result["failed"], result["skipped"],
        )
    except Exception as exc:
        logger.error("LLM analysis failed: %s", exc, exc_info=True)

    return {"new": total_new, "skipped": total_skipped}
