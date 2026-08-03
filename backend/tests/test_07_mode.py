"""
test_07_mode.py — Tests for POST /mode.

/mode does NOT call an LLM ("brain") for its confirmation message — it picks
a random pre-written line from _PROFESSIONAL_LINES / _CASUAL_LINES and only
calls synthesize() (TTS) to voice it. See api/routes/mode.py's own module
docstring: "Confirmation lines are hardcoded — no LLM call needed for a
one-liner." Only `synthesize` needs mocking here to avoid a real audio call.
"""

from unittest.mock import AsyncMock, patch

import pytest

from main import app_state
from core.memory import memory
from api.routes.mode import _PROFESSIONAL_LINES, _CASUAL_LINES, _audio_cache


def _post_mode(client, mode: str):
    return client.post("/mode", json={"mode": mode})


@pytest.fixture(autouse=True)
def _clear_mode_audio_cache():
    """
    mode.py caches synthesized confirmation audio in a module-level dict
    keyed by "text:language" so repeat switches are instant. Clear it
    before and after every test in this file so an earlier test's cached
    entry can never mask whether `synthesize()` was actually invoked (and
    with what text) by the test currently running.
    """
    _audio_cache.clear()
    yield
    _audio_cache.clear()


def test_mode_switch_to_casual_success(client):
    """Switching to 'casual' must return success=True and current_mode='casual',
    and the line spoken must be a genuine casual confirmation line."""
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_mode(client, "casual")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_mode"] == "casual"

    # The text handed to synthesize() must be one of the real casual lines —
    # this is what actually proves the endpoint picked a casual (not
    # professional) confirmation, since ModeResponse never exposes the text.
    spoken_text = mock_tts.call_args.args[0]
    assert spoken_text in _CASUAL_LINES


def test_mode_switch_to_professional_success(client):
    """Switching to 'professional' must return success=True and current_mode='professional',
    and the line spoken must be a genuine professional confirmation line."""
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_mode(client, "professional")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_mode"] == "professional"

    spoken_text = mock_tts.call_args.args[0]
    assert spoken_text in _PROFESSIONAL_LINES


def test_mode_switch_invalid_mode_returns_400(client):
    """Sending an unrecognized mode must return HTTP 400."""
    response = _post_mode(client, "berserker")
    assert response.status_code == 400


def test_mode_switch_clears_memory(client):
    """
    After a mode switch, the memory store must be cleared.
    We verify by adding a message before the switch and checking it's gone.
    """
    memory.add_message("pre-switch-session", "user", "remember me")
    assert len(memory.get_history("pre-switch-session")) == 1

    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        _post_mode(client, "casual")

    # Memory must be cleared
    assert memory.get_history("pre-switch-session") == []


def test_mode_switch_updates_config(client):
    """After a mode switch, app_state['config']['mode'] must reflect the new mode."""
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        _post_mode(client, "casual")

    assert app_state["config"]["mode"] == "casual"

    # Restore
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""
        _post_mode(client, "professional")


def test_mode_switch_returns_confirmation_audio(client):
    """
    The response's 'confirmation_audio' field must be the real base64 audio
    that synthesize() produced for the confirmation line — not merely present
    and string-typed (that alone wouldn't catch it silently returning the
    wrong value, an empty placeholder, or something never actually wired to
    synthesize()'s output).
    """
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = "ZmFrZWF1ZGlv"

        response = _post_mode(client, "casual")

    data = response.json()
    assert "confirmation_audio" in data
    assert isinstance(data["confirmation_audio"], str)
    assert data["confirmation_audio"] == "ZmFrZWF1ZGlv"


def test_mode_switch_case_insensitive(client):
    """The mode value must be lowercased/stripped before validation, and the
    line spoken must still be a genuine casual confirmation line."""
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        # Send with uppercase
        response = client.post("/mode", json={"mode": "CASUAL"})

    assert response.status_code == 200
    assert response.json()["current_mode"] == "casual"

    spoken_text = mock_tts.call_args.args[0]
    assert spoken_text in _CASUAL_LINES


def test_mode_switch_tts_failure_returns_200_with_fallback_audio(client):
    """
    /mode now wraps its synthesize() call in try/except (matching /chat's
    graceful-degradation pattern in api/routes/chat.py) — see
    api/routes/mode.py's switch_mode(). If synthesize() raises, the mode
    switch itself (config + memory, which already happened before this
    call) is NOT rolled back, and the endpoint still returns 200 with
    current_mode correctly set — only confirmation_audio degrades to an
    empty string instead of the request hard-failing with a 500.

    This replaces test_mode_switch_tts_failure_returns_500_with_fallback_body,
    which correctly documented the OLD behavior (no try/except -> raw 500)
    before that gap was fixed. It in turn replaced the original (older still)
    test asserting "brain.generate() failure -> graceful 200 fallback",
    which described a scenario that can't occur at all since /mode never
    calls an LLM.
    """
    with patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.side_effect = RuntimeError("TTS engine offline")

        response = _post_mode(client, "professional")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_mode"] == "professional"
    assert data["confirmation_audio"] == ""

    # The mode switch itself must have genuinely taken effect despite the
    # TTS failure — not just the response claiming success=True.
    assert app_state["config"]["mode"] == "professional"
