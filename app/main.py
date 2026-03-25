"""
main.py — FastAPI Application Entry Point for EurekaNews
=========================================================
Combines the FastAPI web server with APScheduler for periodic RSS fetching
and Telegram bot for user interaction.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from app.core.config import get_settings
from app.core.database import connect_db, close_db
from app.routers import articles, analysis
from app.services.rss_fetcher import run_fetch_cycle
from app.services.telegram_bot import start_telegram_bot, stop_telegram_bot


# ---------------------------------------------------------------------------
# Logging Configuration
# ---------------------------------------------------------------------------
def setup_logging() -> None:
    """Configure structured logging for the application."""
    fmt = "[%(asctime)s] [%(levelname)s] %(name)s — %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("trafilatura").setLevel(logging.WARNING)
    logging.getLogger("feedparser").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("eureka.main")


# ---------------------------------------------------------------------------
# FastAPI Lifespan (startup + shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager:
    - Startup: connect MongoDB, start Telegram bot, run initial fetch, start scheduler.
    - Shutdown: stop scheduler, stop Telegram bot, close MongoDB.
    """
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("EurekaNews Server starting up")
    logger.info("RSSHUB_BASE_URL = %s", settings.rsshub_base_url)
    logger.info("LLM_PROVIDER    = %s", settings.llm_provider)
    logger.info("MongoDB DB      = %s", settings.mongodb_db_name)
    logger.info("Telegram Bot    = %s", "ENABLED" if settings.telegram_bot_token else "DISABLED")
    logger.info("=" * 60)

    # --- Connect to MongoDB ---
    await connect_db()

    # --- Start Telegram bot ---
    await start_telegram_bot()

    # --- Run initial fetch cycle ---
    logger.info("Running initial RSS fetch cycle...")
    await run_fetch_cycle()
    logger.info("Initial fetch cycle completed.")

    # --- Start the scheduler ---
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_fetch_cycle,
        trigger=IntervalTrigger(hours=settings.fetch_interval_hours),
        id="rss_fetch_cycle",
        name=f"RSS Fetch Cycle (every {settings.fetch_interval_hours}h)",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )
    scheduler.start()
    logger.info("Scheduler running — RSS fetch every %d hours.", settings.fetch_interval_hours)

    yield  # Application is running

    # --- Shutdown ---
    logger.info("Shutting down scheduler...")
    scheduler.shutdown(wait=False)
    await stop_telegram_bot()
    await close_db()
    logger.info("EurekaNews Server stopped. Goodbye!")


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="EurekaNews API",
    description="AI-powered news aggregation — RSS fetching, storage, LLM analysis, and Telegram bot.",
    version="3.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(articles.router)
app.include_router(analysis.router)


@app.get("/", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "service": "EurekaNews",
        "status": "running",
        "version": "3.0.0",
    }
