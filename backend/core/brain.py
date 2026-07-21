"""
core/brain.py — Primary LLM interface.

Tries Ollama (llama3) first.  Falls back to Claude claude-opus-4-6 if Ollama is
unreachable or returns an error.  Vision requests always go to Claude.
"""

import logging
import os
from typing import Optional

import httpx
from anthropic import AsyncAnthropic
from dotenv import load_dotenv

from core.memory import memory
from core.prompt_manager import build_system_prompt

load_dotenv()
log = logging.getLogger(__name__)

_OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
_ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

_anthropic = AsyncAnthropic(api_key=_ANTHROPIC_KEY) if _ANTHROPIC_KEY else None


class UltronBrain:
    """Orchestrates LLM calls: Ollama primary → Claude fallback."""

    # ── Text generation ───────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        session_id: str = "default",
        mode: str = "professional",
        language_code: str = "en",
        user_name: str = "sir",
    ) -> str:
        """
        Generate a response for *prompt* using conversation history from
        *session_id*.  Persists the exchange to memory.

        Tries Ollama first; silently falls back to Claude on any error.
        Never raises to the caller.
        """
        if system_prompt is None:
            system_prompt = build_system_prompt(mode, language_code, user_name=user_name)

        history = memory.get_history(session_id)
        messages = history + [{"role": "user", "content": prompt}]

        try:
            response_text = await self._ollama(system_prompt, messages)
        except Exception as ollama_err:
            log.warning("Ollama unavailable (%s), falling back to Claude.", ollama_err)
            try:
                response_text = await self._claude(system_prompt, messages)
            except Exception as claude_err:
                log.error("Claude also failed: %s", claude_err)
                response_text = self._error_response(mode)

        # Persist to memory
        memory.add_message(session_id, "user", prompt)
        memory.add_message(session_id, "assistant", response_text)

        return response_text

    # ── Vision analysis ───────────────────────────────────────────────────────

    async def analyze_image(
        self,
        image_base64: str,
        question: str,
        session_id: str = "default",
        mode: str = "professional",
        language_code: str = "en",
    ) -> str:
        """
        Send a base64-encoded image to Claude Vision along with a question.
        Always uses Claude — Ollama has no vision capability.
        """
        if _anthropic is None:
            return "Vision analysis unavailable — ANTHROPIC_API_KEY not configured."

        system_prompt = build_system_prompt(mode, language_code)

        try:
            message = await _anthropic.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": question},
                        ],
                    }
                ],
            )
            result = message.content[0].text  # type: ignore[union-attr]
        except Exception as err:
            log.error("Claude Vision failed: %s", err)
            result = "I was unable to analyze the image at this time."

        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _ollama(
        self, system_prompt: str, messages: list[dict]
    ) -> str:
        """Call Ollama /api/chat and return the assistant message content."""
        payload = {
            "model": _OLLAMA_MODEL,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "stream": False,
        }
        # connect=5s (localhost, should be instant)
        # read=120s  (llama3 on CPU can take 40-90s on long prompts)
        _timeout = httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)
        async with httpx.AsyncClient(timeout=_timeout) as client:
            resp = await client.post(
                f"{_OLLAMA_BASE}/api/chat", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    async def _claude(
        self, system_prompt: str, messages: list[dict]
    ) -> str:
        """Call Claude claude-opus-4-6 via the Anthropic SDK and return the response text."""
        if _anthropic is None:
            raise RuntimeError("ANTHROPIC_API_KEY not set")

        message = await _anthropic.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            system=system_prompt,
            messages=messages,  # type: ignore[arg-type]
        )
        return message.content[0].text  # type: ignore[union-attr]

    @staticmethod
    def _error_response(mode: str) -> str:
        if mode == "professional":
            return (
                "All inference systems are temporarily offline. "
                "Stand by, sir."
            )
        return (
            "Hmm, I seem to be having some trouble thinking right now. "
            "Give me a moment."
        )


# ── Module-level singleton ────────────────────────────────────────────────────
brain = UltronBrain()
