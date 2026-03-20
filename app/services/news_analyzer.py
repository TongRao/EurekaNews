"""
news_analyzer.py — LLM-Powered News Analysis Pipeline
======================================================
Sends articles to the configured LLM one-by-one, validates the structured
JSON response, and stores the analysis result back in MongoDB.
"""

import json
import logging
from datetime import datetime, timezone

from app.core.database import get_db
from app.models.article import LLMAnalysis
from app.services.llm_client import BaseLLMClient, create_llm_client

logger = logging.getLogger("eureka.news_analyzer")

# ---------------------------------------------------------------------------
# System prompt for the LLM — instructs it to return structured JSON.
# ---------------------------------------------------------------------------
ANALYSIS_SYSTEM_PROMPT = """你是一个专业的新闻分析师。请严格按照以下JSON格式分析新闻内容，不要添加任何额外说明或文字，只返回JSON：

{
    "核心概括": "用一句话概括这条新闻的核心内容",
    "三个关键事实": {
        "谁做了什么": "主要行动方及其行为",
        "为何重要": "这条新闻为什么值得关注",
        "后续动态": "可能的后续发展或影响"
    },
    "利益相关方": {
        "相关方名称1": "该方的立场或受到的影响",
        "相关方名称2": "该方的立场或受到的影响"
    }
}

要求：
1. 必须严格返回上述JSON结构
2. "利益相关方"至少包含2个相关方
3. 用中文回答
4. 不要在JSON外添加任何文字"""


async def analyze_articles(
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 50,
    llm_client: BaseLLMClient | None = None,
) -> dict[str, int]:
    """
    Analyze unanalyzed articles within the given time range.

    For each article:
    1. Send title + content to LLM
    2. Parse response as JSON
    3. Validate against LLMAnalysis pydantic model
    4. On success: store analysis + analyzed_at in MongoDB
    5. On failure: log error and continue

    Args:
        start: Start of time range (optional, defaults to all).
        end: End of time range (optional, defaults to all).
        limit: Maximum number of articles to analyze in one batch.
        llm_client: LLM client instance (auto-created if not provided).

    Returns:
        Summary dict: {"analyzed": N, "failed": M, "skipped": K}.
    """
    db = get_db()
    collection = db["articles"]

    if llm_client is None:
        llm_client = create_llm_client()

    # Build query: unanalyzed articles (no analyzed_at field) in time range
    query: dict = {"analyzed_at": {"$exists": False}}
    if start or end:
        time_filter: dict = {}
        if start:
            time_filter["$gte"] = start
        if end:
            time_filter["$lte"] = end
        query["fetch_time"] = time_filter

    cursor = collection.find(query).sort("fetch_time", -1).limit(limit)
    articles = await cursor.to_list(length=limit)

    if not articles:
        logger.info("No unanalyzed articles found in the given range.")
        return {"analyzed": 0, "failed": 0, "skipped": 0}

    logger.info("Found %d unanalyzed articles. Starting analysis...", len(articles))

    analyzed = 0
    failed = 0
    skipped = 0

    for article in articles:
        article_id = article["_id"]
        title = article.get("title", "")
        content = article.get("content", "")

        # Skip articles with no content
        if not content.strip():
            logger.warning("Skipping article '%s' — empty content.", title)
            skipped += 1
            continue

        # Build LLM input: title + content
        user_input = f"{title}\n\n{content}"

        try:
            # Call the LLM
            raw_response = await llm_client.chat(
                system_prompt=ANALYSIS_SYSTEM_PROMPT,
                user_content=user_input,
            )

            # Parse and validate the JSON response
            analysis_data = _parse_and_validate(raw_response, title)

            if analysis_data is None:
                failed += 1
                continue

            # Store the validated analysis back in MongoDB
            await collection.update_one(
                {"_id": article_id},
                {
                    "$set": {
                        "analysis": analysis_data.model_dump(by_alias=True),
                        "analyzed_at": datetime.now(timezone.utc),
                    }
                },
            )

            analyzed += 1
            logger.info("Analyzed: '%s'", title[:60])

        except Exception as exc:
            logger.error("LLM analysis failed for '%s': %s", title[:60], exc, exc_info=True)
            failed += 1

    logger.info(
        "Analysis batch complete. Analyzed: %d, Failed: %d, Skipped: %d.",
        analyzed, failed, skipped,
    )
    return {"analyzed": analyzed, "failed": failed, "skipped": skipped}


def _parse_and_validate(raw_response: str, title: str) -> LLMAnalysis | None:
    """
    Parse the raw LLM response as JSON and validate it against the
    LLMAnalysis pydantic model.

    Returns:
        A validated LLMAnalysis instance, or None if parsing/validation fails.
    """
    # Clean potential markdown code fences
    text = raw_response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON for '%s': %s\nResponse: %s", title[:60], exc, text[:500])
        return None

    try:
        analysis = LLMAnalysis.model_validate(data)
        return analysis
    except Exception as exc:
        logger.error("LLM JSON missing required fields for '%s': %s\nData: %s", title[:60], exc, data)
        return None
