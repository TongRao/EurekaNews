"""
sample_date — Returns today's date.
=====================================
Triggered when the user message mentions "今天" combined with
keywords like "新闻", "日期", "什么日子", etc.
A simple non-LLM skill demonstrating pure Python logic.
"""

from datetime import date
from typing import Any

from app.skills.base import BaseSkill


class SampleDateSkill(BaseSkill):
    name = "sample_date"
    description = "Returns today's date when the user asks about today."
    triggers = []
    patterns = [
        r"今天.*(新闻|日期|什么日子|几号|星期)",
    ]

    async def execute(self, message: str, context: dict[str, Any]) -> str:
        today = date.today()
        weekday_map = {
            0: "星期一", 1: "星期二", 2: "星期三",
            3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日",
        }
        weekday = weekday_map[today.weekday()]
        return f"今天是 {today.isoformat()}（{weekday}）"
