"""
database.py — MongoDB Connection Manager
=========================================
Async MongoDB connection via motor. Provides connect/close lifecycle hooks
for FastAPI and a get_db() accessor for dependency injection.
"""

import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings

logger = logging.getLogger("eureka.database")

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def connect_db() -> None:
    """
    Open the MongoDB connection and create required indexes.
    Called once during FastAPI startup.
    """
    global _client, _db
    settings = get_settings()

    logger.info("Connecting to MongoDB at %s ...", settings.mongodb_url[:30] + "...")
    _client = AsyncIOMotorClient(settings.mongodb_url)
    _db = _client[settings.mongodb_db_name]

    # Create indexes for the articles collection
    articles = _db["articles"]

    # Unique index on link for deduplication (replaces SQLite dedup store)
    await articles.create_index("link", unique=True)
    # Index on fetch_time for time-range queries
    await articles.create_index("fetch_time")
    # Compound index for category + time-range queries
    await articles.create_index([("category", 1), ("fetch_time", -1)])
    # Sparse index on analyzed_at for finding unanalyzed articles
    await articles.create_index("analyzed_at", sparse=True)

    logger.info("MongoDB connected. Database: %s", settings.mongodb_db_name)


async def close_db() -> None:
    """Close the MongoDB connection. Called during FastAPI shutdown."""
    global _client, _db
    if _client is not None:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed.")


def get_db() -> AsyncIOMotorDatabase:
    """
    Return the active MongoDB database instance.
    Raises RuntimeError if called before connect_db().
    """
    if _db is None:
        raise RuntimeError("Database not initialized. Call connect_db() first.")
    return _db
