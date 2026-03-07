"""Tests for LLM client — chat_completion and chat_completion_json."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.process_analyzer.services.llm_client import (
    chat_completion,
    chat_completion_json,
)


@pytest.fixture
def mock_llm_response():
    """Create a mock httpx response for LLM API."""

    def _make(content: str, status_code: int = 200):
        resp = httpx.Response(
            status_code=status_code,
            json={"choices": [{"message": {"content": content}}]},
            request=httpx.Request("POST", "http://test/chat/completions"),
        )
        return resp

    return _make


class TestChatCompletion:
    @pytest.mark.asyncio
    async def test_returns_stripped_content(self, mock_llm_response):
        mock_resp = mock_llm_response("  Hello World  ")
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await chat_completion("system", "user")
            assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_sends_correct_payload(self, mock_llm_response):
        mock_resp = mock_llm_response("ok")
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            await chat_completion("sys prompt", "user prompt", temperature=0.5, max_tokens=100)

            call_kwargs = instance.post.call_args
            payload = call_kwargs.kwargs["json"]
            assert payload["messages"][0]["content"] == "sys prompt"
            assert payload["messages"][1]["content"] == "user prompt"
            assert payload["temperature"] == 0.5
            assert payload["max_tokens"] == 100

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        error_resp = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("POST", "http://test/chat/completions"),
        )
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = error_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            with pytest.raises(httpx.HTTPStatusError):
                await chat_completion("sys", "user")


class TestChatCompletionJson:
    @pytest.mark.asyncio
    async def test_parses_plain_json(self, mock_llm_response):
        data = {"summary": "test", "steps": []}
        mock_resp = mock_llm_response(json.dumps(data))
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await chat_completion_json("sys", "user")
            assert result == data

    @pytest.mark.asyncio
    async def test_strips_markdown_json_fences(self, mock_llm_response):
        data = {"key": "value"}
        fenced = f"```json\n{json.dumps(data)}\n```"
        mock_resp = mock_llm_response(fenced)
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await chat_completion_json("sys", "user")
            assert result == data

    @pytest.mark.asyncio
    async def test_strips_plain_markdown_fences(self, mock_llm_response):
        data = [{"id": "ap_1"}]
        fenced = f"```\n{json.dumps(data)}\n```"
        mock_resp = mock_llm_response(fenced)
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            result = await chat_completion_json("sys", "user")
            assert result == data

    @pytest.mark.asyncio
    async def test_raises_on_invalid_json(self, mock_llm_response):
        mock_resp = mock_llm_response("not valid json at all")
        with patch("src.process_analyzer.services.llm_client.httpx.AsyncClient") as mock_client:
            instance = AsyncMock()
            instance.post.return_value = mock_resp
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value = instance

            with pytest.raises(json.JSONDecodeError):
                await chat_completion_json("sys", "user")
