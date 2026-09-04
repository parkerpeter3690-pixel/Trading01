"""
Ollama LLM Provider
====================

Local LLM provider using Ollama REST API.
Free, private, no API key needed.

Setup:
    1. Install Ollama: https://ollama.com/download
    2. Pull a model: ollama pull llama3.1:8b
    3. Set OLLAMA_BASE_URL in .env (default: http://localhost:11434)
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from src.agents.llm.base import BaseLLMProvider, LLMMessage, LLMResponse
from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger("agent")


class OllamaProvider(BaseLLMProvider):
    """LLM provider using local Ollama server."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._base_url = base_url or settings.ollama_base_url
        self._model_name = model or settings.ollama_model
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=120.0,
        )

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model(self) -> str:
        return self._model_name

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> LLMResponse:
        """Generate completion via Ollama REST API."""
        start = time.monotonic()

        payload: dict[str, Any] = {
            "model": self._model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if json_mode:
            payload["format"] = "json"

        try:
            response = await self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

            content = data.get("message", {}).get("content", "")
            latency = int((time.monotonic() - start) * 1000)

            # Parse structured output if JSON mode
            structured = None
            if json_mode:
                try:
                    structured = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning("ollama_json_parse_failed", content=content[:200])

            # Token counts from Ollama
            eval_count = data.get("eval_count", 0)
            prompt_eval_count = data.get("prompt_eval_count", 0)

            logger.info(
                "llm_completion",
                provider="ollama",
                model=self._model_name,
                tokens=eval_count + prompt_eval_count,
                latency_ms=latency,
            )

            return LLMResponse(
                content=content,
                structured_output=structured,
                model=self._model_name,
                tokens_used=eval_count + prompt_eval_count,
                prompt_tokens=prompt_eval_count,
                completion_tokens=eval_count,
                cost_estimate=0.0,  # Free (local)
                latency_ms=latency,
            )

        except httpx.HTTPError as e:
            logger.error("ollama_error", error=str(e))
            raise

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/api/tags")
            return response.status_code == 200
        except Exception:
            return False


class OpenAIProvider(BaseLLMProvider):
    """LLM provider using OpenAI API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._model_name = model or settings.openai_model
        self._api_key = api_key or settings.openai_api_key.get_secret_value()

    @property
    def name(self) -> str: return "openai"
    @property
    def model(self) -> str: return self._model_name

    async def complete(self, messages: list[LLMMessage], temperature: float = 0.3,
                       max_tokens: int = 2048, json_mode: bool = False) -> LLMResponse:
        from openai import AsyncOpenAI
        start = time.monotonic()
        client = AsyncOpenAI(api_key=self._api_key)

        kwargs: dict[str, Any] = {
            "model": self._model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        latency = int((time.monotonic() - start) * 1000)
        usage = response.usage

        structured = None
        if json_mode:
            try: structured = json.loads(content)
            except json.JSONDecodeError: pass

        return LLMResponse(
            content=content, structured_output=structured,
            model=self._model_name,
            tokens_used=(usage.total_tokens if usage else 0),
            prompt_tokens=(usage.prompt_tokens if usage else 0),
            completion_tokens=(usage.completion_tokens if usage else 0),
            latency_ms=latency,
        )

    async def health_check(self) -> bool:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self._api_key)
            await client.models.list()
            return True
        except Exception: return False


class GeminiProvider(BaseLLMProvider):
    """LLM provider using Google Gemini API."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self._model_name = model or settings.gemini_model
        self._api_key = api_key or settings.gemini_api_key.get_secret_value()

    @property
    def name(self) -> str: return "gemini"
    @property
    def model(self) -> str: return self._model_name

    async def complete(self, messages: list[LLMMessage], temperature: float = 0.3,
                       max_tokens: int = 2048, json_mode: bool = False) -> LLMResponse:
        from google import genai
        start = time.monotonic()

        client = genai.Client(api_key=self._api_key)

        # Convert messages to Gemini format
        contents = []
        system_instruction = None
        for m in messages:
            if m.role == "system":
                system_instruction = m.content
            else:
                contents.append({"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]})

        config: dict[str, Any] = {"temperature": temperature, "max_output_tokens": max_tokens}
        if json_mode:
            config["response_mime_type"] = "application/json"

        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=contents,
            config=config,
        )

        content = response.text or ""
        latency = int((time.monotonic() - start) * 1000)

        structured = None
        if json_mode:
            try: structured = json.loads(content)
            except json.JSONDecodeError: pass

        tokens = getattr(response, 'usage_metadata', None)
        total_tokens = (tokens.total_token_count if tokens else 0)

        return LLMResponse(
            content=content, structured_output=structured,
            model=self._model_name, tokens_used=total_tokens,
            latency_ms=latency,
        )

    async def health_check(self) -> bool:
        try:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            return True
        except Exception: return False


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to get the configured LLM provider.

    Returns the provider based on LLM_PROVIDER env variable.
    """
    from src.core.config import LLMProvider

    if settings.llm_provider == LLMProvider.OPENAI:
        return OpenAIProvider()
    elif settings.llm_provider == LLMProvider.GEMINI:
        return GeminiProvider()
    else:
        return OllamaProvider()
