"""
user_test — Test skill that calls LLM for a joke.
===================================================
Triggered by the /user_test command.
Calls the configured LLM with "讲一个简短的笑话" and returns
the plain-text response. Used to verify end-to-end Telegram → LLM connectivity.
"""

from typing import Any

from app.skills.base import BaseSkill


class UserTestSkill(BaseSkill):
    name = "user_test"
    description = "Test LLM connectivity by telling a short joke."
    triggers = ["/user_test"]
    patterns = []

    async def execute(self, message: str, context: dict[str, Any]) -> str:
        llm_client = context["llm_client"]

        response = await llm_client.chat(
            system_prompt="你是一个幽默大师，擅长讲简短有趣的笑话。",
            user_content="讲一个简短的笑话",
            json_mode=False,
        )

        return response.strip() if response else "LLM 没有返回内容，请检查连接。"
