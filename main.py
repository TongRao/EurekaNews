#!/usr/bin/env python3
"""
main.py — Entry Point for the EurekaNews RSS Fetching Service
=============================================================
1. Configures structured logging.
2. Runs one immediate full fetch cycle as a smoke test.
3. Schedules recurring fetch cycles every 2 hours via APScheduler.
"""

import logging
import sys

from dotenv import load_dotenv
load_dotenv()  # Load .env before any module reads os.environ

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.rss_fetcher import RSSFetcher, RSSHUB_BASE_URL


def setup_logging() -> None:
    """
    Configure the root logger with a human-readable format.
    INFO level for general progress, ERROR for failures with tracebacks.
    """
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


def main() -> None:
    """Main entry point: immediate fetch + scheduled 2-hour loop."""
    setup_logging()
    logger = logging.getLogger("eureka.main")

    logger.info("=" * 60)
    logger.info("EurekaNews RSS Fetching Service starting up")
    logger.info("RSSHUB_BASE_URL = %s", RSSHUB_BASE_URL)
    logger.info("=" * 60)

    fetcher = RSSFetcher()

    # ------------------------------------------------------------------
    # Phase 1: Run one immediate fetch cycle as a smoke test
    # ------------------------------------------------------------------
    logger.info("Running initial fetch cycle (smoke test)...")
    fetcher.run_fetch_cycle()
    logger.info("Initial fetch cycle completed.")

    # ------------------------------------------------------------------
    # Phase 2: Schedule recurring fetch cycles every 2 hours
    # ------------------------------------------------------------------
    logger.info("Setting up APScheduler — fetch every 2 hours.")
    scheduler = BlockingScheduler()
    scheduler.add_job(
        fetcher.run_fetch_cycle,
        trigger=IntervalTrigger(hours=2),
        id="rss_fetch_cycle",
        name="RSS Fetch Cycle (every 2h)",
        max_instances=1,               # prevent overlapping runs
        coalesce=True,                 # merge missed runs into one
        misfire_grace_time=600,        # 10 min grace for misfires
    )

    try:
        logger.info("Scheduler running. Press Ctrl+C to stop.")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received — stopping scheduler.")
        scheduler.shutdown(wait=False)
        fetcher.close()
        logger.info("EurekaNews RSS Fetching Service stopped. Goodbye!")


if __name__ == "__main__":
    main()
