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

Before running the service, you must configure the infrastructure and environment variables.

### 1.1 Infrastructure Setup (`docker-compose.yml`)

The provided `docker-compose.yml` configures **RSSHub** (for feed proxying) and **MongoDB** (for database storage).

- Open `docker-compose.yml`.
- Locate the `mongodb` service block and **change the default username and password**:
  ```yaml
  MONGO_INITDB_ROOT_USERNAME: your_username
  MONGO_INITDB_ROOT_PASSWORD: your_strong_password
  ```
- Make sure you save the file so your database is secure.

### 1.2 Environment Variables (`.env`)

Copy the example configuration to create your active `.env` file:
```bash
cp .env.example .env
```

Open `.env` and configure your endpoints and credentials:

| Variable | Description | Example |
|---|---|---|
| `RSSHUB_BASE_URL` | Base URL of your RSSHub instance | `http://100.x.x.x:1200` |
| `MONGODB_URL` | Connection string **matching your docker-compose username and password** | `mongodb://your_username:your_strong_password@127.0.0.1:27017` |
| `LLM_PROVIDER` | `ollama` or `openai` | `ollama` |
| `OLLAMA_BASE_URL` | Base URL of your Ollama instance | `http://100.y.y.y:11434` |
| `OPENAI_API_KEY` | Key for commercial APIs (if provider=openai) | `sk-...` |

---

## 2. Running the Infrastructure

Once configured, start the background infrastructure (RSSHub, Redis, MongoDB, Browserless) in detached mode:

```bash
docker compose up -d
```

Verify that the containers are running with `docker ps`.

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
