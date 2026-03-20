"""
config.py — Centralized Settings for EurekaNews
================================================
All environment-dependent configuration is managed here via pydantic-settings.
Values are loaded from .env file (via python-dotenv) or system environment.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- RSSHub ---
    rsshub_base_url: str = "http://localhost:1200"

    # --- MongoDB ---
    mongodb_url: str = "mongodb://ai_admin:your_strong_password_2026@127.0.0.1:27017"
    mongodb_db_name: str = "eureka_news"

    # --- LLM ---
    llm_provider: str = "ollama"  # "ollama" or "openai"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"

    # OpenAI-compatible (for future commercial APIs)
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # --- Scheduler ---
    fetch_interval_hours: int = 2


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton of the application settings."""
    return Settings()
