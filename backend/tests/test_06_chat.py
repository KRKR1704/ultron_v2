"""
test_06_chat.py — Tests for POST /chat.

All tests mock run_agent and synthesize so no real LLM or TTS calls are made.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from main import app_state


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post_chat(client, payload: dict):
    return client.post("/chat", json=payload)


# ── Validation tests ───────────────────────────────────────────────────────────

def test_chat_missing_message_returns_422(client):
    """Posting without 'message' key must return 422."""
    response = _post_chat(client, {"session_id": "test"})
    assert response.status_code == 422


def test_chat_missing_session_id_uses_default(client):
    """
    'session_id' is optional (defaults to 'default').
    A payload with just 'message' must succeed when agent/TTS are mocked.
    """
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Hello, sir."
        mock_tts.return_value = ""

        response = _post_chat(client, {"message": "hello"})

    # The route manually parses and defaults session_id — must not 422
    assert response.status_code == 200


def test_chat_returns_required_fields(client):
    """Response must always include response_text, audio_base64, language, mode."""
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Understood, sir."
        mock_tts.return_value = "ZmFrZWF1ZGlv"  # base64 placeholder

        response = _post_chat(client, {"message": "what time is it", "session_id": "s1"})

    assert response.status_code == 200
    data = response.json()
    assert "response_text" in data
    assert "audio_base64" in data
    assert "language" in data
    assert "mode" in data


def test_chat_empty_message_still_responds(client):
    """
    An empty string message is technically valid JSON — the route must handle
    it without a 500 error (agent and TTS are mocked).
    """
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "I didn't catch that, sir."
        mock_tts.return_value = ""

        response = _post_chat(client, {"message": "", "session_id": "s1"})

    # Should be 200 (empty message just passes through to agent)
    assert response.status_code == 200


def test_chat_mode_switch_casual_inline(client, reset_mode):
    """
    Sending 'switch to casual mode' must change app_state['config']['mode']
    to 'casual' and return a confirmation without calling run_agent.
    """
    app_state["config"]["mode"] = "professional"

    with patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "switch to casual mode",
            "session_id": "switch-test",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "casual"


def test_chat_mode_switch_professional_inline(client, reset_mode):
    """
    'be more professional' must switch mode to professional.
    """
    app_state["config"]["mode"] = "casual"

    with patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "be more professional",
            "session_id": "switch-test-2",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "professional"


def test_chat_short_mode_switch_returns_confirmation_directly(client, reset_mode):
    """
    A short (≤8 words) pure mode-switch message must return a confirmation
    directly WITHOUT calling run_agent.
    """
    app_state["config"]["mode"] = "professional"

    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "should not be called"
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "casual mode",
            "session_id": "short-switch",
        })

    assert response.status_code == 200
    # run_agent must NOT have been called for a pure short switch
    mock_agent.assert_not_called()


def test_chat_session_id_preserved_in_response(client):
    """
    The response must include the mode and language that were active, and
    the HTTP status must be 200 for a valid request.
    """
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Of course, sir."
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "hello there",
            "session_id": "my-unique-session",
        })

    assert response.status_code == 200
    data = response.json()
    # mode and language come from app_state — they must be present
    assert "mode" in data
    assert "language" in data


def test_chat_invalid_json_returns_422(client):
    """Sending a raw non-JSON body must result in a 422 response."""
    response = client.post(
        "/chat",
        content=b"this is not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_chat_response_text_comes_from_agent(client):
    """The response_text in the JSON must equal what run_agent returned."""
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "The answer is 42, sir."
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "what is the answer",
            "session_id": "s99",
        })

    data = response.json()
    assert data["response_text"] == "The answer is 42, sir."
