"""
telegram_bot.py — Telegram Bot Service
========================================
Integrates with Telegram via python-telegram-bot (v20+ async).
Routes incoming messages through the SkillRegistry and replies
with the skill's response.

Uses polling mode — no public HTTPS endpoint required.
"""

import logging
from typing import Any

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.core.config import get_settings
from app.services.llm_client import create_llm_client
from app.skills.registry import SkillRegistry

logger = logging.getLogger("eureka.telegram_bot")

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_application: Application | None = None
_registry: SkillRegistry | None = None
_skill_context: dict[str, Any] = {}


# ===========================================================================
# Message Handlers
# ===========================================================================
async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Universal message handler.
    Routes every incoming text message through the SkillRegistry.
    """
    if not update.message or not update.message.text:
        return

    user_msg = update.message.text.strip()
    user_name = update.message.from_user.first_name if update.message.from_user else "Unknown"
    logger.info("Message from %s: %s", user_name, user_msg[:100])

    if _registry is None:
        await update.message.reply_text("⚠️ Bot is still initializing, please try again later.")
        return

    # Try to match a skill
    skill = _registry.match(user_msg)

    if skill is None:
        await update.message.reply_text(
            "🤔 我还不知道怎么处理这个请求。\n"
            "可用命令:\n"
            + "\n".join(f"  {t}" for s in _registry.skills for t in s.triggers if s.triggers)
        )
        return

    logger.info("Matched skill: %s", skill.name)

    try:
        response = await skill.execute(user_msg, _skill_context)
        await update.message.reply_text(response)
    except Exception as exc:
        logger.error("Skill '%s' execution failed: %s", skill.name, exc, exc_info=True)
        await update.message.reply_text(f"❌ 执行出错: {exc}")


async def _handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command — show welcome message."""
    if not update.message:
        return

    skills_list = "\n".join(
        f"  • {s.name} — {s.description}"
        for s in (_registry.skills if _registry else [])
    )

    await update.message.reply_text(
        "👋 欢迎使用 EurekaNews Bot!\n\n"
        f"已加载的技能:\n{skills_list}\n\n"
        "发送命令或自然语言消息来与我互动。"
    )


# ===========================================================================
# Lifecycle
# ===========================================================================
async def start_telegram_bot() -> None:
    """
    Initialize and start the Telegram bot with polling.
    Called during FastAPI startup.
    """
    global _application, _registry, _skill_context

    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled.")
        return

    # Initialize the skill registry
    _registry = SkillRegistry()
    _registry.discover()

    # Build the shared context for skills
    _skill_context = {
        "llm_client": create_llm_client(),
        "settings": settings,
    }

    # Build the Telegram application
    _application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Register handlers
    _application.add_handler(CommandHandler("start", _handle_start))
    # MessageHandler for ALL text (including /commands that aren't /start)
    _application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message))
    # Also handle commands not explicitly registered (like /user_test)
    _application.add_handler(MessageHandler(filters.COMMAND, _handle_message))

    # Start polling (non-blocking)
    await _application.initialize()
    await _application.start()
    await _application.updater.start_polling(drop_pending_updates=True)

    logger.info("Telegram bot started (polling mode). %d skills loaded.", len(_registry.skills))


async def stop_telegram_bot() -> None:
    """
    Gracefully stop the Telegram bot.
    Called during FastAPI shutdown.
    """
    global _application

    if _application is None:
        return

    logger.info("Stopping Telegram bot...")
    await _application.updater.stop()
    await _application.stop()
    await _application.shutdown()
    _application = None
    logger.info("Telegram bot stopped.")
