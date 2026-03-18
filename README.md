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

本项目依赖 [RSSHub](https://docs.rsshub.app/) 作为统一的 RSS 源代理（默认监听 `localhost:1200`）。推荐使用 Docker Compose 部署。

在项目根目录或服务器上创建 `docker-compose.yml`：

```yaml
version: '3'

services:
    rsshub:
        image: diygod/rsshub:latest
        restart: always
        ports:
            # 将 100.x.x.x 替换为你的 Tailscale IP
            # 这样 RSSHub 只在 Tailscale 内网监听，隔绝公网
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
# 启动 RSSHub
docker compose up -d

# 验证运行状态
curl http://localhost:1200
```

> **Note**: 如果不使用 Tailscale，可将端口配置简化为 `"1200:1200"`（仅本机访问）或 `"127.0.0.1:1200:1200"`。

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
