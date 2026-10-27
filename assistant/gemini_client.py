"""Google Gemini API client using official google-genai SDK."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GeminiError(Exception):
    """Base exception for Gemini API interactions."""
    pass


class GeminiTimeout(GeminiError):
    """Raised when Gemini API request times out."""
    pass


class GeminiAuthError(GeminiError):
    """Raised when Gemini API key or credentials are invalid."""
    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class GeminiLimitError(GeminiError):
    """Raised when quota or rate limits are exceeded."""
    def __init__(
        self,
        detail: str = "",
        resets_at: Optional[float] = None,
        reset_text: str = "",
    ) -> None:
        msg = "Gemini quota or rate limit reached"
        if reset_text:
            msg = f"{msg} (resets {reset_text})"
        super().__init__(msg)
        self.detail = detail
        self.resets_at = resets_at
        self.reset_text = reset_text


class GeminiClient:
    """Async client wrapper for Google Gemini generation."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        model: str = "gemini-3.8-flash",
        timeout: int = 60,
        auth_label: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = max(1, timeout)
        self._auth_label = auth_label

    @property
    def auth_mode(self) -> str:
        if self._auth_label:
            return self._auth_label
        return "API key from .env" if self.api_key else "not configured"

    def __repr__(self) -> str:
        return f"GeminiClient(model={self.model!r}, timeout={self.timeout}, auth_mode={self.auth_mode!r})"

    def _get_client(self) -> Any:
        from google import genai
        if not self.api_key:
            raise GeminiAuthError("Gemini API key is not configured. Set GEMINI_API_KEY in .env.")
        return genai.Client(api_key=self.api_key)

    async def run(self, prompt: str, system_prompt: str) -> str:
        """Call Gemini model asynchronously with timeout and error handling."""
        from google.genai import errors, types

        client = self._get_client()
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.7,
        )

        try:
            coro = client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            response = await asyncio.wait_for(coro, timeout=float(self.timeout))
            text = response.text or ""
            return text.strip()
        except asyncio.TimeoutError:
            raise GeminiTimeout(f"Gemini API request timed out after {self.timeout}s")
        except errors.APIError as e:
            code = getattr(e, "code", None)
            msg = str(e)
            if code == 429 or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                raise GeminiLimitError(detail=msg) from e
            if code in (401, 403) or "API_KEY_INVALID" in msg or "PERMISSION_DENIED" in msg:
                raise GeminiAuthError(f"Gemini authentication failed: {msg}", detail=msg) from e
            raise GeminiError(f"Gemini API error ({code}): {msg}") from e
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                raise GeminiLimitError(detail=msg) from e
            if "API_KEY_INVALID" in msg or "401" in msg or "403" in msg:
                raise GeminiAuthError(f"Gemini authentication failed: {msg}", detail=msg) from e
            raise GeminiError(f"Unexpected Gemini error: {msg}") from e

    async def inspect(self) -> Dict[str, Any]:
        """Diagnostic ping to verify Gemini API connection."""
        if not self.api_key:
            return {
                "auth": self.auth_mode,
                "status": "error",
                "error": "GEMINI_API_KEY is not set",
                "model": self.model,
            }

        try:
            reply = await self.run(prompt="ping", system_prompt="Reply with exactly: OK")
            return {
                "auth": self.auth_mode,
                "status": "ok",
                "model": self.model,
                "reply": reply,
            }
        except Exception as e:
            return {
                "auth": self.auth_mode,
                "status": "error",
                "model": self.model,
                "error": str(e),
            }
