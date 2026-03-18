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

## Prerequisites — RSSHub

This project relies on [RSSHub](https://docs.rsshub.app/) as a unified RSS feed proxy (listening on `localhost:1200` by default). Docker Compose is the recommended way to deploy it.

Create a `docker-compose.yml` on your server or project root:

```yaml
version: '3'

services:
    rsshub:
        image: diygod/rsshub:latest
        restart: always
        ports:
            # Replace 100.x.x.x with your Tailscale IP
            # This ensures RSSHub only listens on your Tailscale private network
            - "100.x.x.x:1200:1200"
        environment:
            NODE_ENV: production
            CACHE_TYPE: redis
            REDIS_URL: 'redis://redis:6379/'
            PUPPETEER_WS_ENDPOINT: 'ws://browserless:3000'
        depends_on:
            - redis
            - browserless

    browserless:
        image: browserless/chrome:latest
        restart: always
        ulimits:
          core:
            hard: 0
            soft: 0

    redis:
        image: redis:alpine
        restart: always
        volumes:
            - redis-data:/data

volumes:
    redis-data:
```

```bash
# Start RSSHub
docker compose up -d

# Verify it's running
curl http://localhost:1200
```

> **Note**: If you're not using Tailscale, simplify the port mapping to `"1200:1200"` or `"127.0.0.1:1200:1200"` for local-only access.

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure RSSHub endpoint
cp .env.example .env
# Edit .env and set RSSHUB_BASE_URL to your RSSHub instance address

# 4. Run the service
python3 main.py
# Runs an immediate fetch, then loops every 2 hours. Ctrl+C to stop.
```

## Configuration

Feed URLs in `config/feeds_config.json` use **relative paths** for RSSHub routes (e.g., `/apnews/topics/apf-topnews`) and full URLs for direct RSS sources (e.g., WSJ). The RSSHub host is injected at runtime via environment variable, keeping the config portable across environments:

| Environment | `RSSHUB_BASE_URL` |
|---|---|
| Local dev (RSSHub on same machine) | `http://localhost:1200` (default) |
| Server via Tailscale | `http://100.x.x.x:1200` |
| Docker same-host network | `http://rsshub:1200` |

Set the variable in your `.env` file (gitignored) or export it directly:

```bash
export RSSHUB_BASE_URL=http://100.x.x.x:1200
```

## Project Structure

```
EurekaNews/
├── config/
│   └── feeds_config.json    # Feed source configuration (paths + strategies)
├── data/                    # Auto-created at runtime (gitignored)
│   ├── dedup.db             # SQLite dedup database
│   └── raw_data_YYYYMMDD.jsonl
├── src/
│   └── rss_fetcher.py       # Core fetcher module
├── main.py                  # Entry point
├── requirements.txt         # Python dependencies
├── .env.example             # Environment variable template
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
