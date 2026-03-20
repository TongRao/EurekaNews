"""
llm_client.py — Abstract LLM Client with Ollama & OpenAI Support
=================================================================
Provider-agnostic interface for calling LLMs. Supports local Ollama
deployments and any OpenAI-compatible commercial API.
"""

import json
import logging
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings, get_settings

logger = logging.getLogger("eureka.llm_client")


# ===========================================================================
# Abstract Base
# ===========================================================================
class BaseLLMClient(ABC):
    """Interface that all LLM providers must implement."""

    @abstractmethod
    async def chat(self, system_prompt: str, user_content: str) -> str:
        """
        Send a chat request and return the raw text response.

        Args:
            system_prompt: Instructions for the LLM (role: system).
            user_content: The actual content to process (role: user).

        Returns:
            Raw text response from the LLM.
        """
        ...


# ===========================================================================
# Ollama Client
# ===========================================================================
class OllamaClient(BaseLLMClient):
    """
    Client for local Ollama deployments.
    Calls POST /api/chat on the Ollama server.
    """

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        logger.info("OllamaClient initialized: %s (model: %s)", self.base_url, self.model)

    async def chat(self, system_prompt: str, user_content: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "stream": False,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()

        data = resp.json()
        return data.get("message", {}).get("content", "")


# ===========================================================================
# OpenAI-Compatible Client
# ===========================================================================
class OpenAIClient(BaseLLMClient):
    """
    Client for any OpenAI-compatible API (OpenAI, DeepSeek, etc.).
    Calls POST /chat/completions with Bearer token auth.
    """

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        logger.info("OpenAIClient initialized: %s (model: %s)", self.base_url, self.model)

    async def chat(self, system_prompt: str, user_content: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return ""


# ===========================================================================
# Factory
# ===========================================================================
def create_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    """
    Create the appropriate LLM client based on LLM_PROVIDER setting.

    Returns:
        An instance of OllamaClient or OpenAIClient.
    """
    if settings is None:
        settings = get_settings()

    provider = settings.llm_provider.lower()

    if provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )
    elif provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIClient(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: '{provider}'. Must be 'ollama' or 'openai'.")
