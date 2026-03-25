# EurekaNews 📰

AI-powered news aggregation system — v3 with Telegram Bot & Skill System.

## Overview

A robust backend service that powers the EurekaNews AI aggregation system. It periodically pulls articles from configured RSS sources, persists raw data to MongoDB, provides REST APIs for data retrieval, and connects to Telegram as a user-facing interface with a modular skill system for extensible message handling.

## Features

- **FastAPI Core** — Async native, high-performance web server with auto-generated OpenAPI docs.
- **Background Fetching** — APScheduler integration runs RSS fetch cycles automatically (default every 2h).
- **MongoDB Storage** — Fast time-range querying and robust deduplication via unique index.
- **Provider-Agnostic LLM** — Built-in support for local Ollama deployments or any OpenAI-compatible commercial API.
- **Structured AI Analysis** — Automated LLM pipeline after each fetch cycle, extracting key facts into structured JSON.
- **Telegram Bot** — User-facing interface via Telegram (polling mode), routes messages through the skill system.
- **Modular Skill System** — Plugin architecture with auto-discovery. Add new skills by creating a folder — no existing code changes needed.

---

## 1. Configuration (Important)

All configuration is consolidated into a single `.env` file. The `docker-compose.yml` is completely static and reads from your environment automatically.

### 1.1 Environment Setup (`.env`)

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
| `TELEGRAM_BOT_TOKEN` | Bot token from Telegram @BotFather | `123456:ABC-DEF...` |

---

## 2. Running the Infrastructure

```bash
docker compose up -d
```

**🔑 Viewing your Data:**
Visit `http://127.0.0.1:8081` to access Mongo-Express (login credentials configurable in `.env`).

---

## 3. Running the FastAPI Application

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On startup, the server automatically: connects to MongoDB → starts the Telegram bot → runs an initial RSS fetch + LLM analysis → starts the scheduler.

API docs at `http://localhost:8000/docs`.

---

## Skill System

Skills are modular, auto-discovered plugins located in `app/skills/`. Each skill is a folder containing a `skill.py` file with a class that extends `BaseSkill`.

### Adding a New Skill

1. Create a new folder: `app/skills/my_skill/`
2. Add `__init__.py` (empty) and `skill.py`
3. In `skill.py`, subclass `BaseSkill`:

```python
from app.skills.base import BaseSkill

class MySkill(BaseSkill):
    name = "my_skill"
    description = "Does something cool."
    triggers = ["/my_command"]          # Exact command match
    patterns = [r"keyword.*pattern"]    # Regex for natural language

    async def execute(self, message, context):
        # context["llm_client"], context["settings"] available
        return "Hello from my skill!"
```

4. Restart the server — the skill is auto-discovered and registered.

### Built-in Skills

| Skill | Trigger | Description |
|---|---|---|
| `user_test` | `/user_test` | Calls LLM to tell a joke (connectivity test) |
| `sample_date` | "今天有什么新闻" | Returns today's date |

---

## API Endpoints

### Articles

*All endpoints accept `start` / `end` (ISO 8601), `category`, `feed_id`, `skip`, and `limit` query parameters.*

- `GET /api/articles/titles` — Lightweight list of articles within a time range.
- `GET /api/articles/summaries` — Returns titles + full text content.
- `GET /api/articles/full` — Returns all fields, including completed LLM analysis.

### Analysis

- `POST /api/analysis/run` — Triggers a background analysis job. Responds immediately.
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
│   ├── services/
│   │   ├── rss_fetcher.py   # RSS fetching & processing logic
│   │   ├── llm_client.py    # Abstract LLM client (Ollama / Others)
│   │   ├── news_analyzer.py # LLM prompting & JSON validation
│   │   └── telegram_bot.py  # Telegram bot (polling mode)
│   └── skills/              # Modular skill system (auto-discovered)
│       ├── base.py          # BaseSkill abstract class
│       ├── registry.py      # Auto-discovery & dispatch
│       ├── user_test/       # /user_test → LLM joke
│       └── sample_date/     # "今天" → date
├── config/
│   └── feeds_config.json    # RSS feed configurations
├── docker-compose.yml       # Infrastructure (RSSHub + MongoDB)
├── .env.example             # Configuration template
└── requirements.txt         # Python dependencies
```
