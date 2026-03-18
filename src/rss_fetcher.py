"""
rss_fetcher.py — Core RSS Data Fetching Service for EurekaNews
==============================================================
A lightweight, robust RSS fetching module that supports three configurable
fetch strategies, SQLite-based deduplication, and daily JSONL persistence.
"""

import json
import logging
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger("eureka.rss_fetcher")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Root directory of the project (two levels up from src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "feeds_config.json"
DATA_DIR = PROJECT_ROOT / "data"

HTTP_TIMEOUT = 15  # seconds for all outbound HTTP requests


# ===========================================================================
# Configuration Loader
# ===========================================================================
def load_feeds_config(config_path: Path = CONFIG_PATH) -> list[dict[str, Any]]:
    """
    Load and return only the *active* feed entries from feeds_config.json.

    Raises:
        FileNotFoundError: if the config file does not exist.
        json.JSONDecodeError: if the config file is malformed.
    """
    logger.info("Loading feed configuration from %s", config_path)
    with open(config_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    all_feeds = data.get("feeds", [])
    active_feeds = [f for f in all_feeds if f.get("active", False)]
    logger.info(
        "Found %d feeds total, %d active.", len(all_feeds), len(active_feeds)
    )
    return active_feeds


# ===========================================================================
# Deduplication Store (SQLite-backed)
# ===========================================================================
class DeduplicationStore:
    """
    A thin SQLite wrapper that tracks which articles have already been
    processed, keyed on (feed_id, link).  The database file is created
    automatically on first use.
    """

    def __init__(self, db_path: Path | None = None):
        if db_path is None:
            db_path = DATA_DIR / "dedup.db"

        # Ensure the parent directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL;")  # safer for concurrent access
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_articles (
                feed_id  TEXT NOT NULL,
                link     TEXT NOT NULL,
                seen_at  TEXT NOT NULL,
                PRIMARY KEY (feed_id, link)
            );
            """
        )
        self._conn.commit()
        logger.info("Deduplication store ready at %s", db_path)

    def is_seen(self, feed_id: str, link: str) -> bool:
        """Return True if this (feed_id, link) pair was already recorded."""
        cursor = self._conn.execute(
            "SELECT 1 FROM seen_articles WHERE feed_id = ? AND link = ?",
            (feed_id, link),
        )
        return cursor.fetchone() is not None

    def mark_seen(self, feed_id: str, link: str) -> None:
        """Record a (feed_id, link) pair so future checks return True."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_articles (feed_id, link, seen_at) VALUES (?, ?, ?)",
            (feed_id, link, now),
        )
        self._conn.commit()

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


# ===========================================================================
# HTML Cleaning Utility
# ===========================================================================
def strip_html(raw_html: str | None) -> str:
    """
    Remove all HTML tags from *raw_html* using BeautifulSoup, preserving
    meaningful whitespace and newlines.  Returns an empty string when the
    input is None or blank.
    """
    if not raw_html:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")

    # Replace <br>, <p>, <div> boundaries with newlines for readability
    for br_tag in soup.find_all("br"):
        br_tag.replace_with("\n")
    for block_tag in soup.find_all(["p", "div", "li"]):
        block_tag.insert_before("\n")
        block_tag.insert_after("\n")

    text = soup.get_text()

    # Collapse excessive blank lines but keep paragraph breaks
    lines = [line.strip() for line in text.splitlines()]
    cleaned = "\n".join(line for line in lines if line)
    return cleaned.strip()


# ===========================================================================
# Fetch Strategies
# ===========================================================================
def fetch_full_rss(entry: feedparser.FeedParserDict) -> str:
    """
    FULL_RSS strategy — extract content directly from the RSS entry's
    description / content field and strip HTML.
    """
    # feedparser normalises content into entry.get("content", [])
    content_blocks = entry.get("content", [])
    if content_blocks:
        raw = content_blocks[0].get("value", "")
    else:
        raw = entry.get("description", "") or entry.get("summary", "")
    return strip_html(raw)


def fetch_scrape_web(entry: feedparser.FeedParserDict) -> str:
    """
    SCRAPE_WEB strategy — follow the article link and extract the full
    article body using trafilatura with favor_precision=True for clean output.
    Falls back to the RSS description if scraping fails.
    """
    link = entry.get("link", "")
    if not link:
        logger.warning("SCRAPE_WEB: entry has no link, falling back to RSS body.")
        return fetch_full_rss(entry)

    try:
        # Use trafilatura's own downloader for robust page retrieval
        downloaded = trafilatura.fetch_url(link)
        if downloaded:
            text = trafilatura.extract(downloaded, favor_precision=True)
            if text:
                return text.strip()

        # If trafilatura returns nothing, try requests + trafilatura.extract
        logger.warning(
            "trafilatura.fetch_url returned nothing for %s, trying requests.",
            link,
        )
        resp = requests.get(link, timeout=HTTP_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; EurekaNews/1.0)"
        })
        resp.raise_for_status()
        text = trafilatura.extract(resp.text, favor_precision=True)
        if text:
            return text.strip()

    except Exception as exc:
        logger.error("SCRAPE_WEB failed for %s: %s", link, exc, exc_info=True)

    # Ultimate fallback: use whatever the RSS feed provides
    logger.warning("Falling back to RSS description for %s", link)
    return fetch_full_rss(entry)


def fetch_summary_only(entry: feedparser.FeedParserDict) -> str:
    """
    SUMMARY_ONLY strategy — for paywalled sources, simply concatenate the
    title and the stripped description.  No outbound web requests are made.
    """
    title = entry.get("title", "").strip()
    desc = strip_html(entry.get("description", "") or entry.get("summary", ""))
    parts = [p for p in (title, desc) if p]
    return "\n\n".join(parts)


# Strategy dispatcher keyed on the config value
STRATEGY_MAP = {
    "FULL_RSS": fetch_full_rss,
    "SCRAPE_WEB": fetch_scrape_web,
    "SUMMARY_ONLY": fetch_summary_only,
}


# ===========================================================================
# JSONL Writer
# ===========================================================================
class JSONLWriter:
    """
    Appends one JSON object per line to a daily-rotated .jsonl file inside
    the ``data/`` directory.
    """

    def __init__(self, data_dir: Path = DATA_DIR):
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)

    def _today_path(self) -> Path:
        """Return the path for today's JSONL file, e.g. raw_data_20260317.jsonl."""
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        return self._data_dir / f"raw_data_{date_str}.jsonl"

    def write(self, record: dict[str, Any]) -> None:
        """Append a single JSON record as one line to today's file."""
        path = self._today_path()
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()  # explicit flush for durability on high-frequency writes


# ===========================================================================
# Main Orchestrator
# ===========================================================================
class RSSFetcher:
    """
    Top-level orchestrator that ties together configuration, strategies,
    deduplication, and persistence.
    """

    def __init__(self) -> None:
        self.dedup = DeduplicationStore()
        self.writer = JSONLWriter()

    def run_fetch_cycle(self) -> None:
        """
        Execute one full fetch cycle: load config → iterate feeds →
        parse RSS → apply strategy → dedup → persist.

        Errors within a single feed are caught and logged; they never
        crash the main process.
        """
        logger.info("=" * 60)
        logger.info("Starting new fetch cycle at %s", datetime.now(timezone.utc).isoformat())
        logger.info("=" * 60)

        try:
            feeds = load_feeds_config()
        except Exception as exc:
            logger.error("Failed to load feed configuration: %s", exc, exc_info=True)
            return

        total_new = 0
        total_skipped = 0

        for feed_cfg in feeds:
            feed_id = feed_cfg["id"]
            feed_name = feed_cfg.get("name", feed_id)
            feed_url = feed_cfg["url"]
            strategy_name = feed_cfg.get("fetch_strategy", "FULL_RSS")
            category = feed_cfg.get("category", "")

            logger.info("--- Processing feed: %s (%s) [%s] ---", feed_name, feed_id, strategy_name)

            try:
                new, skipped = self._process_feed(
                    feed_id=feed_id,
                    feed_url=feed_url,
                    strategy_name=strategy_name,
                    category=category,
                )
                total_new += new
                total_skipped += skipped
                logger.info(
                    "Feed %s done: %d new articles, %d duplicates skipped.",
                    feed_id, new, skipped,
                )
            except Exception as exc:
                logger.error(
                    "Feed %s (%s) FAILED — skipping. Error: %s",
                    feed_name, feed_url, exc,
                    exc_info=True,
                )

        logger.info(
            "Fetch cycle complete. Total new: %d, Total skipped: %d.",
            total_new, total_skipped,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _process_feed(
        self,
        feed_id: str,
        feed_url: str,
        strategy_name: str,
        category: str,
    ) -> tuple[int, int]:
        """
        Parse a single RSS feed and process every entry.
        Returns (new_count, skipped_count).
        """
        # Resolve the fetch strategy function
        strategy_fn = STRATEGY_MAP.get(strategy_name)
        if strategy_fn is None:
            logger.warning(
                "Unknown fetch_strategy '%s' for feed %s, falling back to FULL_RSS.",
                strategy_name, feed_id,
            )
            strategy_fn = fetch_full_rss

        # Parse the RSS feed with feedparser
        parsed = feedparser.parse(feed_url)

        if parsed.bozo and not parsed.entries:
            # bozo flag means feedparser encountered an error; but if entries
            # still exist we can usually proceed.
            raise RuntimeError(
                f"feedparser could not parse {feed_url}: {parsed.bozo_exception}"
            )

        entries = parsed.entries
        logger.info("Parsed %d entries from %s", len(entries), feed_url)

        new_count = 0
        skipped_count = 0

        for entry in entries:
            link = entry.get("link", "")
            title = entry.get("title", "(no title)")

            if not link:
                logger.warning("Skipping entry with no link: %s", title)
                continue

            # --- Deduplication check ---
            if self.dedup.is_seen(feed_id, link):
                skipped_count += 1
                continue

            # --- Apply the chosen fetch strategy ---
            try:
                content = strategy_fn(entry)
            except Exception as exc:
                logger.error(
                    "Strategy %s failed for entry '%s' (%s): %s",
                    strategy_name, title, link, exc,
                    exc_info=True,
                )
                content = ""

            if not content:
                logger.warning("Empty content for '%s' — writing record anyway.", title)

            # --- Build the output record ---
            record = {
                "fetch_id": str(uuid.uuid4()),
                "feed_id": feed_id,
                "category": category,
                "title": title,
                "link": link,
                "content": content,
                "fetch_time": datetime.now(timezone.utc).isoformat(),
            }

            # --- Write to JSONL & mark as seen ---
            self.writer.write(record)
            self.dedup.mark_seen(feed_id, link)
            new_count += 1

        return new_count, skipped_count

    def close(self) -> None:
        """Release resources held by the fetcher (DB connections, etc.)."""
        self.dedup.close()
        logger.info("RSSFetcher resources released.")
