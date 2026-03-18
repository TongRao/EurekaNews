# EurekaNews 📰

AI-powered news aggregation system — RSS data pipeline layer.

## Overview

A lightweight, robust RSS fetching service that powers the EurekaNews AI news aggregation system. It periodically pulls articles from configured RSS sources, intelligently extracts full-text content, deduplicates, and persists raw data for downstream AI processing.

## Features

- **Configuration-driven** — all feed sources managed via `config/feeds_config.json`
- **Three fetch strategies** — `FULL_RSS` (inline content), `SCRAPE_WEB` (full article extraction), `SUMMARY_ONLY` (paywalled sources)
- **SQLite deduplication** — prevents duplicate article storage
- **Daily JSONL output** — appends to `data/raw_data_YYYYMMDD.jsonl`
- **Scheduled execution** — APScheduler runs fetch cycles every 2 hours
- **Fault-tolerant** — per-feed error isolation; failures never crash the service

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the service
python3 main.py
# Runs an immediate fetch, then loops every 2 hours. Ctrl+C to stop.
```

## Project Structure

```
EurekaNews/
├── config/
│   └── feeds_config.json    # Feed source configuration
├── data/                    # Auto-created at runtime (gitignored)
│   ├── dedup.db             # SQLite dedup database
│   └── raw_data_YYYYMMDD.jsonl
├── src/
│   └── rss_fetcher.py       # Core fetcher module
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
└── .gitignore
```

## Output Format

Each line in the JSONL output is a JSON object:

```json
{
  "fetch_id": "UUID",
  "feed_id": "ap_news_world",
  "category": "国际时政",
  "title": "Article title",
  "link": "https://...",
  "content": "Cleaned full-text content",
  "fetch_time": "2026-03-17T01:36:31+00:00"
}
```

## Tech Stack

Python 3.10+ · feedparser · BeautifulSoup4 · trafilatura · APScheduler
