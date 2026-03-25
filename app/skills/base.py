"""
base.py — BaseSkill Abstract Class
====================================
Every skill in EurekaNews must subclass BaseSkill and implement
the execute() method. Skills are auto-discovered by the SkillRegistry.
"""

import re
from abc import ABC, abstractmethod
from typing import Any


class BaseSkill(ABC):
    """
    Abstract base class for all skills.

    Attributes:
        name: Unique identifier for this skill (e.g. "user_test").
        description: Human-readable description of what the skill does.
        triggers: List of exact command strings (e.g. ["/user_test"]).
        patterns: List of regex pattern strings for natural language matching.
    """

    name: str = ""
    description: str = ""
    triggers: list[str] = []
    patterns: list[str] = []

    @abstractmethod
    async def execute(self, message: str, context: dict[str, Any]) -> str:
        """
        Process the user message and return a text response.

        Args:
            message: The raw user message text.
            context: Shared services dict containing:
                - "llm_client": BaseLLMClient instance
                - "db": AsyncIOMotorDatabase instance
                - "settings": Settings instance

        Returns:
            A text string to send back to the user.
        """
        ...

    def matches_trigger(self, message: str) -> bool:
        """Check if the message matches any exact command trigger."""
        text = message.strip().lower()
        return any(text == t.lower() or text.startswith(t.lower() + " ") for t in self.triggers)

    def matches_pattern(self, message: str) -> bool:
        """Check if the message matches any regex pattern."""
        for pattern in self.patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return True
        return False
