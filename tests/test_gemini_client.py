"""Unit tests for GeminiClient exception classification, timeouts, and inspecting."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from assistant.gemini_client import (
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiLimitError,
    GeminiTimeout,
)


@pytest.mark.asyncio
async def test_client_requires_api_key():
    """Client raises GeminiAuthError if api_key is None or empty."""
    client = GeminiClient(api_key=None)
    with pytest.raises(GeminiAuthError, match="not configured"):
        await client.run("hello", "sys")


@pytest.mark.asyncio
async def test_successful_run():
    """Verify standard response text extraction from mock genai client."""
    client = GeminiClient(api_key="AIzaSyMock")

    mock_resp = MagicMock()
    mock_resp.text = "Salom! Men yordamchiman."

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(return_value=mock_resp)

    mock_genai_client = MagicMock()
    mock_genai_client.aio.models = mock_aio_models

    with patch.object(client, "_get_client", return_value=mock_genai_client):
        reply = await client.run("Salom", "Sen assistentsan")
        assert reply == "Salom! Men yordamchiman."
        mock_aio_models.generate_content.assert_called_once()


@pytest.mark.asyncio
async def test_client_timeout():
    """Verify GeminiTimeout is raised when call exceeds timeout."""
    client = GeminiClient(api_key="AIzaSyMock", timeout=1)

    async def slow_call(*args, **kwargs):
        await asyncio.sleep(2)

    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = slow_call
    mock_genai_client = MagicMock()
    mock_genai_client.aio.models = mock_aio_models

    with patch.object(client, "_get_client", return_value=mock_genai_client):
        with pytest.raises(GeminiTimeout):
            await client.run("Salom", "sys")


@pytest.mark.asyncio
async def test_rate_limit_and_auth_classification():
    """Verify quota and auth errors are cleanly classified."""
    client = GeminiClient(api_key="AIzaSyMock")

    # Resource exhausted / 429
    mock_aio_models = MagicMock()
    mock_aio_models.generate_content = AsyncMock(side_effect=Exception("429 RESOURCE_EXHAUSTED: Quota exceeded"))
    mock_genai_client = MagicMock()
    mock_genai_client.aio.models = mock_aio_models

    with patch.object(client, "_get_client", return_value=mock_genai_client):
        with pytest.raises(GeminiLimitError):
            await client.run("prompt", "sys")

    # Invalid API key
    mock_aio_models.generate_content = AsyncMock(side_effect=Exception("API_KEY_INVALID: API key not valid"))
    with patch.object(client, "_get_client", return_value=mock_genai_client):
        with pytest.raises(GeminiAuthError):
            await client.run("prompt", "sys")


@pytest.mark.asyncio
async def test_inspect_status():
    """Verify inspect() returns status dict without throwing."""
    # Without key
    c_empty = GeminiClient(api_key=None)
    res_empty = await c_empty.inspect()
    assert res_empty["status"] == "error"

    # With key and success
    c_ok = GeminiClient(api_key="AIzaSyMock")
    with patch.object(c_ok, "run", AsyncMock(return_value="OK")):
        res_ok = await c_ok.inspect()
        assert res_ok["status"] == "ok"
        assert res_ok["reply"] == "OK"
