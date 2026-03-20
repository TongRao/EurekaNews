"""
analysis.py — LLM Analysis API Endpoints
==========================================
Endpoints for triggering and monitoring LLM-powered news analysis.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Query

from app.core.database import get_db
from app.services.news_analyzer import analyze_articles

logger = logging.getLogger("eureka.api.analysis")

router = APIRouter(prefix="/api/analysis", tags=["Analysis"])


# ===========================================================================
# POST /api/analysis/run
# ===========================================================================
@router.post("/run")
async def trigger_analysis(
    background_tasks: BackgroundTasks,
    start: Optional[datetime] = Query(None, description="Start of time range (ISO 8601)"),
    end: Optional[datetime] = Query(None, description="End of time range (ISO 8601)"),
    limit: int = Query(50, ge=1, le=500, description="Max articles to analyze per batch"),
):
    """
    Trigger LLM analysis for unanalyzed articles in the given time range.

    Analysis runs as a background task so the API responds immediately.
    Use GET /api/analysis/status to monitor progress.
    """
    background_tasks.add_task(analyze_articles, start=start, end=end, limit=limit)

    return {
        "status": "accepted",
        "message": f"Analysis task started for up to {limit} articles.",
        "params": {
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "limit": limit,
        },
    }


# ===========================================================================
# GET /api/analysis/status
# ===========================================================================
@router.get("/status")
async def get_analysis_status(
    start: Optional[datetime] = Query(None, description="Start of time range"),
    end: Optional[datetime] = Query(None, description="End of time range"),
):
    """
    Get the count of analyzed vs unanalyzed articles, optionally filtered
    by time range.
    """
    db = get_db()
    collection = db["articles"]

    # Build time filter
    time_filter: dict = {}
    if start or end:
        tf: dict = {}
        if start:
            tf["$gte"] = start
        if end:
            tf["$lte"] = end
        time_filter["fetch_time"] = tf

    # Total articles
    total = await collection.count_documents(time_filter or {})

    # Analyzed articles
    analyzed_query = {**time_filter, "analyzed_at": {"$exists": True}}
    analyzed = await collection.count_documents(analyzed_query)

    # Unanalyzed
    unanalyzed = total - analyzed

    return {
        "total": total,
        "analyzed": analyzed,
        "unanalyzed": unanalyzed,
        "coverage": f"{analyzed / total * 100:.1f}%" if total > 0 else "0%",
    }
