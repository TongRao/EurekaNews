# EurekaNews 📰

AI-powered news aggregation system — v2 FastAPI Backend.

## Overview

A robust backend service that powers the EurekaNews AI aggregation system. It periodically pulls articles from configured RSS sources, persists raw data to MongoDB, and provides REST APIs to trigger and retrieve AI-powered news analysis using local (Ollama) or commercial (OpenAI-compatible) LLMs.

## Features

- **FastAPI Core** — Async native, high-performance web server with auto-generated OpenAPI docs.
- **Background Fetching** — APScheduler integration runs RSS fetch cycles automatically (default every 2h).
- **MongoDB Storage** — Replaces fragile flat files; provides fast time-range querying and robust deduplication.
- **Provider-Agnostic LLM** — Built-in support for local Ollama deployments or OpenAI-compatible commercial APIs.
- **Structured AI Analysis** — Asynchronous LLM pipeline that extracts key facts, summaries, and stakeholders into structured JSON.
- **Configuration-Driven** — Feed sources managed via JSON, environment configuration via `.env`.

---

## Prerequisites

This backend requires two external services to function:
1. **RSSHub** (for unified feed proxying)
2. **MongoDB** (for data storage)

We recommend using Docker Compose. Create a `docker-compose.yml` on your server:

```yaml
version: '3'

services:
    rsshub:
        image: diygod/rsshub:latest
        restart: always
        ports:
            # Replace 127.0.0.1 with your Tailscale IP if needed
            - "127.0.0.1:1200:1200"
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

    mongodb:
        image: mongo:latest
        restart: always
        environment:
            MONGO_INITDB_ROOT_USERNAME: ai_admin
            # Change this password!
            MONGO_INITDB_ROOT_PASSWORD: your_strong_password_2026
        ports:
            - "127.0.0.1:27017:27017"
        volumes:
            - mongodb-data:/data/db

volumes:
    redis-data:
    mongodb-data:
```

```bash
docker compose up -d
```

---

## Configuration

Copy the example environment file:
```bash
cp .env.example .env
```

Edit the `.env` file to configure your endpoints and credentials:

| Variable | Description | Example |
|---|---|---|
| `RSSHUB_BASE_URL` | Base URL of your RSSHub instance | `http://100.x.x.x:1200` |
| `MONGODB_URL` | Connection string matching your docker-compose | `mongodb://ai_admin:pass@127.0.0.1:27017` |
| `LLM_PROVIDER` | `ollama` or `openai` | `ollama` |
| `OLLAMA_BASE_URL` | Base URL of your Ollama instance | `http://100.y.y.y:11434` |
| `OPENAI_API_KEY` | Key for commercial APIs (if provider=openai) | `sk-...` |

---

## Quick Start

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

*Note: On startup, the server automatically runs an initial RSS fetch cycle and connects to MongoDB. You can access the interactive API documentation at `http://localhost:8000/docs`.*

---

## API Endpoints

### Articles

*All endpoints accept `start` / `end` (ISO 8601), `category`, `feed_id`, `skip`, and `limit` query parameters.*

- `GET /api/articles/titles` — Lightweight list of articles within a time range.
- `GET /api/articles/summaries` — Returns titles + full text content.
- `GET /api/articles/full` — Returns all fields, including completed LLM analysis.

### Analysis

- `POST /api/analysis/run` — Triggers a background job to run LLM analysis on unanalyzed articles in the specified time range. Responds immediately.
- `GET /api/analysis/status` — Returns the count of analyzed vs. unanalyzed articles.

---

## Project Structure

```
EurekaNews/
├── app/
│   ├── main.py              # FastAPI application & lifespan
│   ├── core/
│   │   ├── config.py        # Environment variables (Pydantic Settings)
│   │   └── database.py      # Async MongoDB connection
│   ├── models/
│   │   └── article.py       # Pydantic schemas (+ LLM JSON aliases)
│   ├── routers/
│   │   ├── articles.py      # Article query endpoints
│   │   └── analysis.py      # Analysis trigger endpoints
│   └── services/
│       ├── rss_fetcher.py   # RSS fetching & processing logic
│       ├── llm_client.py    # Abstract Ollama/OpenAI client
│       └── news_analyzer.py # LLM prompting & JSON validation
├── config/
│   └── feeds_config.json    # RSS feed configurations
├── docker-compose.yml       # Infrastructure (RSSHub + MongoDB)
├── .env.example             # Configuration template
└── requirements.txt         # Python dependencies
```
