"""
registry.py — Skill Registry with Auto-Discovery
===================================================
Scans app/skills/*/skill.py at startup, imports all BaseSkill subclasses,
and provides a match() method that routes user messages to the right skill.
"""

import importlib
import logging
from pathlib import Path
from typing import Any

from app.skills.base import BaseSkill

logger = logging.getLogger("eureka.skills.registry")

# Directory containing all skill sub-packages
SKILLS_DIR = Path(__file__).resolve().parent


class SkillRegistry:
    """
    Central registry that discovers, stores, and dispatches skills.

    Usage:
        registry = SkillRegistry()
        registry.discover()                   # Scan and register all skills
        skill = registry.match(user_message)  # Find matching skill
        if skill:
            response = await skill.execute(message, context)
    """

    def __init__(self) -> None:
        self._skills: list[BaseSkill] = []

    @property
    def skills(self) -> list[BaseSkill]:
        """Return all registered skills."""
        return list(self._skills)

    def register(self, skill: BaseSkill) -> None:
        """Manually register a skill instance."""
        self._skills.append(skill)
        logger.info("Registered skill: %s (%s)", skill.name, skill.description)

    def discover(self) -> None:
        """
        Auto-discover skills by scanning app/skills/*/skill.py.

        Each skill.py module must contain at least one class that
        subclasses BaseSkill. All such classes are instantiated and
        registered automatically.
        """
        logger.info("Discovering skills in %s ...", SKILLS_DIR)

        for child in sorted(SKILLS_DIR.iterdir()):
            # Skip non-directories and internal files
            if not child.is_dir() or child.name.startswith("_"):
                continue

            skill_file = child / "skill.py"
            if not skill_file.exists():
                continue

            module_path = f"app.skills.{child.name}.skill"
            try:
                module = importlib.import_module(module_path)
            except Exception as exc:
                logger.error("Failed to import skill module %s: %s", module_path, exc, exc_info=True)
                continue

            # Find all BaseSkill subclasses in the module
            found = False
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseSkill)
                    and attr is not BaseSkill
                ):
                    try:
                        instance = attr()
                        self.register(instance)
                        found = True
                    except Exception as exc:
                        logger.error("Failed to instantiate skill %s: %s", attr_name, exc, exc_info=True)

            if not found:
                logger.warning("No BaseSkill subclass found in %s", module_path)

        logger.info("Skill discovery complete. %d skills registered.", len(self._skills))

    def match(self, message: str) -> BaseSkill | None:
        """
        Find the first skill that matches the given user message.

        Matching priority:
        1. Exact command trigger (e.g. /user_test)
        2. Regex pattern match (first match wins)

        Returns:
            The matching BaseSkill instance, or None if no match.
        """
        # Priority 1: exact command triggers
        for skill in self._skills:
            if skill.matches_trigger(message):
                return skill

        # Priority 2: regex pattern matches
        for skill in self._skills:
            if skill.matches_pattern(message):
                return skill

        return None
