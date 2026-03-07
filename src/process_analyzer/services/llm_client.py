from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from src.process_analyzer import config

logger = logging.getLogger(__name__)


async def chat_completion(
    system: str,
    user: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    temperature = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tokens = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS

    payload = {
        "model": config.LLM_MODEL,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{config.LLM_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()

    content: str = data["choices"][0]["message"]["content"]
    return content.strip()


async def chat_completion_json(
    system: str,
    user: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> Any:
    raw = await chat_completion(system, user, temperature, max_tokens)

    # Strip markdown fences if present
    cleaned = raw
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        cleaned = cleaned[first_newline + 1 :]
    if cleaned.endswith("```"):
        cleaned = cleaned[: cleaned.rfind("```")]
    cleaned = cleaned.strip()

    return json.loads(cleaned)
