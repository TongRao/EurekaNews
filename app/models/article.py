"""
article.py — Pydantic Models for Articles and LLM Analysis
===========================================================
Defines request/response schemas and the MongoDB document structure.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ===========================================================================
# LLM Analysis sub-document
# ===========================================================================
class KeyFacts(BaseModel):
    """Three key facts extracted by the LLM."""
    who_did_what: str = Field(..., alias="谁做了什么")
    why_important: str = Field(..., alias="为何重要")
    follow_up: str = Field(..., alias="后续动态")

    model_config = {"populate_by_name": True}


class LLMAnalysis(BaseModel):
    """Structured analysis result returned by the LLM."""
    core_summary: str = Field(..., alias="核心概括")
    briefing: str = Field(..., alias="简报")
    key_facts: KeyFacts = Field(..., alias="三个关键事实")
    stakeholders: dict[str, str] = Field(..., alias="利益相关方")

    model_config = {"populate_by_name": True}


# ===========================================================================
# API Response Models
# ===========================================================================
class ArticleTitle(BaseModel):
    """Lightweight response: titles only."""
    id: str = Field(..., alias="_id")
    feed_id: str
    category: str
    title: str
    link: str
    fetch_time: datetime

    model_config = {"populate_by_name": True}


class ArticleSummary(ArticleTitle):
    """Medium response: titles + content."""
    content: str = ""


class ArticleFull(ArticleSummary):
    """Full response: all fields including analysis."""
    analysis: Optional[LLMAnalysis] = None
    analyzed_at: Optional[datetime] = None


# ===========================================================================
# Query Parameters
# ===========================================================================
class TimeRangeParams(BaseModel):
    """Common query parameters for time-range article lookups."""
    start: datetime
    end: datetime
    category: Optional[str] = None
    feed_id: Optional[str] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)
