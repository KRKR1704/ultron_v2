"""
test_08_voice.py — Tests for POST /voice (STT → agent → TTS pipeline).

Mocks the STT transcription functions so no real Whisper model is needed.
"""

from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

@dataclass
class _FakeSTTResult:
    transcript: str
    language: str = "English"
    language_code: str = "en"


def _post_voice(client, payload: dict):
    return client.post("/voice", json=payload)


# ── Validation tests ───────────────────────────────────────────────────────────

def test_voice_missing_audio_returns_422(client):
    """Posting without 'audio_base64' must return 422."""
    response = _post_voice(client, {"session_id": "test"})
    assert response.status_code == 422


def test_voice_with_valid_base64_audio_returns_text(client, test_audio_base64):
    """
    Providing a valid base64 audio payload must return a response with text fields.
    STT and agent are mocked.
    """
    fake_result = _FakeSTTResult(
        transcript="What time is it?",
        language="English",
        language_code="en",
    )

    with patch("api.routes.voice.transcribe_base64", return_value=fake_result), \
         patch("api.routes.voice.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "It is 3 PM, sir."
        mock_tts.return_value = ""

        response = _post_voice(client, {
            "audio_base64": test_audio_base64,
            "session_id": "voice-test",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "What time is it?"
    assert data["response_text"] == "It is 3 PM, sir."


def test_voice_response_has_required_fields(client, test_audio_base64):
    """Voice response must include transcript, response_text, audio_base64, language, mode."""
    fake_result = _FakeSTTResult(transcript="Hello", language="English", language_code="en")

    with patch("api.routes.voice.transcribe_base64", return_value=fake_result), \
         patch("api.routes.voice.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Hello to you too."
        mock_tts.return_value = "ZmFrZQ=="

        response = _post_voice(client, {
            "audio_base64": test_audio_base64,
            "session_id": "v1",
        })

    data = response.json()
    for field in ("transcript", "response_text", "audio_base64", "language", "mode"):
        assert field in data, f"Missing field in voice response: {field!r}"


def test_voice_empty_audio_handled_gracefully(client):
    """
    An empty audio_base64 string must be handled gracefully —
    the STT layer returns empty transcript, which triggers the fallback.
    """
    empty_result = _FakeSTTResult(transcript="", language="English", language_code="en")

    with patch("api.routes.voice.transcribe_base64", return_value=empty_result), \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_voice(client, {
            "audio_base64": "",
            "session_id": "empty-audio",
        })

    # Must return 200 with a fallback message, not 500
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data.get("response_text"), str)
    assert len(data["response_text"]) > 0  # fallback text must be present


def test_voice_detected_language_used_in_response(client, test_audio_base64):
    """
    When STT detects a non-English language, the response language field
    must reflect the detected language, not the config default.
    """
    hindi_result = _FakeSTTResult(
        transcript="नमस्ते",
        language="Hindi",
        language_code="hi",
    )

    with patch("api.routes.voice.transcribe_base64", return_value=hindi_result), \
         patch("api.routes.voice.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "नमस्ते, सर।"
        mock_tts.return_value = ""

        response = _post_voice(client, {
            "audio_base64": test_audio_base64,
            "session_id": "hindi-session",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "hi"
