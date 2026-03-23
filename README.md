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

## 1. Configuration (Important)

We have consolidated all configuration into a single environment file. The `docker-compose.yml` file is now completely static and reads credentials directly from your environment to prevent git conflicts.

### 1.1 Environment Setup (`.env`)

Copy the example configuration to create your active `.env` file:
```bash
cp .env.example .env
```

Open `.env` and configure your credentials and endpoints:

| Variable | Description | Example |
|---|---|---|
| `RSSHUB_BASE_URL` | Base URL of your RSSHub instance | `http://100.x.x.x:1200` |
| `MONGO_INITDB_ROOT_USERNAME` | MongoDB superuser username | `ai_admin` |
| `MONGO_INITDB_ROOT_PASSWORD` | MongoDB superuser password (**Change this!**) | `SuperSecret2026` |
| `MONGODB_URL` | MongoDB Connection URI (interpolates the above) | `mongodb://${MONGO_INITDB_ROOT_USERNAME}...` |
| `MONGO_EXPRESS_USERNAME` | Web UI login username for viewing the database | `admin` |
| `MONGO_EXPRESS_PASSWORD` | Web UI login password for viewing the database | `my_secure_web_pass` |
| `LLM_PROVIDER` | `ollama` or `others` | `ollama` |
| `OLLAMA_BASE_URL` | Base URL of your Ollama instance | `http://100.y.y.y:11434` |
| `OTHERS_API_KEY` | Key for commercial APIs (if provider=others) | `sk-...` |
| `OTHERS_BASE_URL` | Base URL of your commercial API (e.g. DeepSeek, Kimi) | `https://api.deepseek.com/v1` |

---

## 2. Running the Infrastructure

Once configured, start the background infrastructure (RSSHub, Redis, MongoDB, Mongo-Express, Browserless) in detached mode:

```bash
docker compose up -d
```

Verify that the containers are running with `docker ps`.

**🔑 Viewing your Data:**
We included `mongo-express` in the stack so you can view your MongoDB data natively in your browser.
1. Visit `http://127.0.0.1:8081` in your browser.
2. Login with Username: `admin` | Password: `password` (configurable in `docker-compose.yml`).
3. Click into the `eureka_news` database and then the `articles` collection to see your fetched feeds and LLM analysis results.

---

## 3. Running the FastAPI Application

Now that the infrastructure is up, start the main backend application:

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
