"""LLM service with connection pooling and fallback."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from openai import APIConnectionError, APIError, RateLimitError

logger = logging.getLogger(__name__)

# Global requests session for connection pooling
_requests_session = None


def _get_requests_session():
    """Get or create global requests session."""
    global _requests_session
    if _requests_session is None:
        import requests
        _requests_session = requests.Session()
        _requests_session.verify = False
        _requests_session.headers.update({
            'Authorization': 'Bearer 5a52e6f001524b2f92f99477c4514d99.lbKAltd7qQTp7Wk6',
            'Content-Type': 'application/json',
            'User-Agent': 'AutoSlides/1.0',
        })
        logger.info("Created global requests session")
    return _requests_session


class LLMService:
    """Unified wrapper for any OpenAI-compatible endpoint."""

    def __init__(self, base_url: str, api_key: str, model_name: str):
        self.base_url = base_url
        self.api_key = api_key
        self.model = model_name
        # Don't create AsyncOpenAI client initially, use requests by default
        self.client = None

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 16384,
        **kwargs,
    ) -> str:
        """Non-streaming chat completion using requests."""
        try:
            # Directly use requests for better reliability
            return await self._chat_with_requests(
                messages, temperature, max_tokens, **kwargs
            )
        except (APIError, RateLimitError) as e:
            logger.error("LLM API error for model %s: %s", self.model, str(e)[:500])
            # Try to extract content from error response if available
            if hasattr(e, 'body') and e.body:
                try:
                    error_body = json.loads(e.body) if isinstance(e.body, str) else e.body
                    logger.error("LLM error body: %s", error_body)
                except:
                    pass
            raise

    async def _chat_with_requests(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 16384,
        **kwargs,
    ) -> str:
        """Implementation using requests library."""

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            **kwargs,
        }

        # Run requests in executor to avoid blocking
        def make_request():
            session = _get_requests_session()
            session.headers['Authorization'] = f"Bearer {self.api_key}"
            # 增加超时时间到300秒（5分钟），给agent更多时间完成
            resp = session.post(url, json=payload, timeout=300)
            resp.raise_for_status()
            return resp.json()

        try:
            data = await asyncio.to_thread(make_request)
            return data["choices"][0]["message"].get("content", "")
        except Exception as e:
            logger.error("Requests call failed: %s", str(e)[:500])
            raise APIConnectionError(f"Requests call failed: {e}")

    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 16384,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Yields streaming tokens."""
        # Streaming not implemented with requests, raise error
        raise NotImplementedError("Streaming not supported with requests backend")

    async def json_chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 16384,
        **kwargs,
    ) -> str:
        """Chat completion with JSON output mode."""
        return await self.chat(
            messages, temperature, max_tokens, response_format={"type": "json_object"}, **kwargs
        )
