"""
test_16_brain.py — Tests for core/brain.py UltronBrain.

Mocks httpx calls (Ollama) and the Anthropic SDK client so no real
LLM requests are made.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from core.brain import UltronBrain


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_brain() -> UltronBrain:
    """Return a fresh UltronBrain instance for isolation."""
    return UltronBrain()


def _mock_ollama_response(text: str) -> MagicMock:
    """Build a mock httpx response that returns a valid Ollama JSON body."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "message": {"content": text, "role": "assistant"},
        "done": True,
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_anthropic_message(text: str) -> MagicMock:
    """Build a mock Anthropic message object."""
    mock_content = MagicMock()
    mock_content.text = text

    mock_message = MagicMock()
    mock_message.content = [mock_content]
    return mock_message


# ── generate() tests ──────────────────────────────────────────────────────────

async def test_brain_generate_with_mock_ollama():
    """generate() must call Ollama and return the assistant message content."""
    brain = _make_brain()
    expected = "Understood, sir. The capital of France is Paris."
    mock_resp = _mock_ollama_response(expected)

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.post = AsyncMock(return_value=mock_resp)

    with patch("core.brain.httpx.AsyncClient", return_value=mock_async_client):
        result = await brain.generate(
            prompt="What is the capital of France?",
            session_id="brain-test-1",
            mode="professional",
            language_code="en",
        )

    assert result == expected
    assert isinstance(result, str)


async def test_brain_falls_back_to_claude_when_ollama_fails():
    """
    When Ollama raises (connection error), brain must silently fall back
    to Claude and return the Claude response.
    """
    brain = _make_brain()
    claude_response = "Claude fallback: the answer is 42."
    mock_claude_message = _mock_anthropic_message(claude_response)

    # Make Ollama fail
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.post = AsyncMock(
        side_effect=httpx.ConnectError("Ollama is offline")
    )

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create = AsyncMock(return_value=mock_claude_message)

    with patch("core.brain.httpx.AsyncClient", return_value=mock_async_client), \
         patch("core.brain._anthropic", mock_anthropic_instance):
        result = await brain.generate(
            prompt="What is the answer?",
            session_id="brain-test-2",
            mode="professional",
            language_code="en",
        )

    assert result == claude_response


async def test_brain_generate_returns_string():
    """generate() must always return a str (even on full failure)."""
    brain = _make_brain()

    # Both Ollama and Claude fail
    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.post = AsyncMock(side_effect=RuntimeError("Ollama down"))

    with patch("core.brain.httpx.AsyncClient", return_value=mock_async_client), \
         patch("core.brain._anthropic", None):  # no Claude fallback either
        result = await brain.generate(
            prompt="test",
            session_id="brain-test-3",
        )

    assert isinstance(result, str)
    assert len(result) > 0  # error response must be non-empty


async def test_brain_analyze_image_calls_claude_vision():
    """analyze_image() must call the Anthropic Vision API and return its response."""
    brain = _make_brain()
    vision_response = "I see a cat sitting on a keyboard."
    mock_message = _mock_anthropic_message(vision_response)

    mock_anthropic_instance = MagicMock()
    mock_anthropic_instance.messages.create = AsyncMock(return_value=mock_message)

    with patch("core.brain._anthropic", mock_anthropic_instance):
        result = await brain.analyze_image(
            image_base64="ZmFrZWltYWdl",
            question="What do you see?",
            session_id="vision-test",
            mode="professional",
            language_code="en",
        )

    assert result == vision_response
    mock_anthropic_instance.messages.create.assert_called_once()


async def test_brain_analyze_image_without_api_key_returns_message():
    """
    analyze_image() with no Anthropic client must return a polite unavailability
    message instead of raising.
    """
    brain = _make_brain()

    with patch("core.brain._anthropic", None):
        result = await brain.analyze_image(
            image_base64="ZmFrZWltYWdl",
            question="What's in the image?",
        )

    assert isinstance(result, str)
    assert "unavailable" in result.lower() or "not configured" in result.lower()


async def test_brain_generate_persists_to_memory():
    """After generate(), the exchange must be stored in memory."""
    from core.memory import ConversationMemory

    brain = _make_brain()
    test_session = "memory-test-brain-789"
    expected = "I have computed the answer."
    mock_resp = _mock_ollama_response(expected)

    mock_async_client = AsyncMock()
    mock_async_client.__aenter__ = AsyncMock(return_value=mock_async_client)
    mock_async_client.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.post = AsyncMock(return_value=mock_resp)

    with patch("core.brain.httpx.AsyncClient", return_value=mock_async_client):
        await brain.generate(
            prompt="What is the answer?",
            session_id=test_session,
        )

    from core.memory import memory
    history = memory.get_history(test_session)
    assert len(history) >= 2
    assert history[-2]["role"] == "user"
    assert history[-1]["role"] == "assistant"
    assert history[-1]["content"] == expected

    # Cleanup
    memory.clear_session(test_session)


async def test_brain_error_response_professional_mode():
    """_error_response in professional mode must reference 'sir' or 'offline'."""
    result = UltronBrain._error_response("professional")
    assert isinstance(result, str)
    lower = result.lower()
    assert "offline" in lower or "sir" in lower or "systems" in lower


async def test_brain_error_response_casual_mode():
    """_error_response in casual mode must be friendly in tone."""
    result = UltronBrain._error_response("casual")
    assert isinstance(result, str)
    assert len(result) > 0
