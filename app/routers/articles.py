"""
articles.py — Article Query API Endpoints
==========================================
GET endpoints for querying articles from MongoDB by time range,
with three levels of detail: titles, summaries, and full.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query

from app.core.database import get_db

logger = logging.getLogger("eureka.api.articles")

router = APIRouter(prefix="/api/articles", tags=["Articles"])


# ===========================================================================
# Shared query builder
# ===========================================================================
def _build_time_query(
    start: datetime,
    end: datetime,
    category: Optional[str] = None,
    feed_id: Optional[str] = None,
) -> dict:
    """Build a MongoDB filter dict from common query parameters."""
    query: dict = {
        "fetch_time": {"$gte": start, "$lte": end},
    }
    if category:
        query["category"] = category
    if feed_id:
        query["feed_id"] = feed_id
    return query


# ===========================================================================
# GET /api/articles/titles
# ===========================================================================
@router.get("/titles")
async def get_article_titles(
    start: datetime = Query(..., description="Start of time range (ISO 8601)"),
    end: datetime = Query(..., description="End of time range (ISO 8601)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    feed_id: Optional[str] = Query(None, description="Filter by feed ID"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max results to return"),
):
    """
    Return article titles and metadata (no content) within a time range.
    Lightweight endpoint for listing/browsing.
    """
    db = get_db()
    query = _build_time_query(start, end, category, feed_id)

    projection = {
        "_id": 1, "feed_id": 1, "category": 1,
        "title": 1, "link": 1, "fetch_time": 1,
    }

    cursor = (
        db["articles"]
        .find(query, projection)
        .sort("fetch_time", -1)
        .skip(skip)
        .limit(limit)
    )
    articles = await cursor.to_list(length=limit)

    # Convert _id to string for JSON serialization
    for a in articles:
        a["_id"] = str(a["_id"])

    total = await db["articles"].count_documents(query)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "articles": articles,
    }


# ===========================================================================
# GET /api/articles/summaries
# ===========================================================================
@router.get("/summaries")
async def get_article_summaries(
    start: datetime = Query(..., description="Start of time range (ISO 8601)"),
    end: datetime = Query(..., description="End of time range (ISO 8601)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    feed_id: Optional[str] = Query(None, description="Filter by feed ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Return article titles + content within a time range.
    This is the default view for LLM input preparation.
    """
    db = get_db()
    query = _build_time_query(start, end, category, feed_id)

    projection = {
        "_id": 1, "feed_id": 1, "category": 1,
        "title": 1, "link": 1, "content": 1, "fetch_time": 1,
    }

    cursor = (
        db["articles"]
        .find(query, projection)
        .sort("fetch_time", -1)
        .skip(skip)
        .limit(limit)
    )
    articles = await cursor.to_list(length=limit)

    for a in articles:
        a["_id"] = str(a["_id"])

    total = await db["articles"].count_documents(query)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "articles": articles,
    }


# ===========================================================================
# GET /api/articles/full
# ===========================================================================
@router.get("/full")
async def get_articles_full(
    start: datetime = Query(..., description="Start of time range (ISO 8601)"),
    end: datetime = Query(..., description="End of time range (ISO 8601)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    feed_id: Optional[str] = Query(None, description="Filter by feed ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Return all article fields including LLM analysis results.
    Full view for detailed inspection and debugging.
    """
    db = get_db()
    query = _build_time_query(start, end, category, feed_id)

    # No projection — return all fields
    cursor = (
        db["articles"]
        .find(query)
        .sort("fetch_time", -1)
        .skip(skip)
        .limit(limit)
    )
    articles = await cursor.to_list(length=limit)

    for a in articles:
        a["_id"] = str(a["_id"])

    total = await db["articles"].count_documents(query)

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "articles": articles,
    }
