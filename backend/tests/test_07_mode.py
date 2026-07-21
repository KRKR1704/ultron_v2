"""
test_07_mode.py — Tests for POST /mode.

Mocks brain.generate and synthesize to avoid real LLM/TTS calls.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from main import app_state
from core.memory import memory


def _post_mode(client, mode: str):
    return client.post("/mode", json={"mode": mode})


def test_mode_switch_to_casual_success(client):
    """Switching to 'casual' must return success=True and current_mode='casual'."""
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Casual mode on!")
        mock_tts.return_value = ""

        response = _post_mode(client, "casual")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_mode"] == "casual"


def test_mode_switch_to_professional_success(client):
    """Switching to 'professional' must return success=True and current_mode='professional'."""
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Professional mode reactivated, sir.")
        mock_tts.return_value = ""

        response = _post_mode(client, "professional")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["current_mode"] == "professional"


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

    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Switching now.")
        mock_tts.return_value = ""

        _post_mode(client, "casual")

    # Memory must be cleared
    assert memory.get_history("pre-switch-session") == []


def test_mode_switch_updates_config(client):
    """After a mode switch, app_state['config']['mode'] must reflect the new mode."""
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Done.")
        mock_tts.return_value = ""

        _post_mode(client, "casual")

    assert app_state["config"]["mode"] == "casual"

    # Restore
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Done.")
        mock_tts.return_value = ""
        _post_mode(client, "professional")


def test_mode_switch_returns_confirmation_audio(client):
    """The response must include a 'confirmation_audio' field (may be empty string)."""
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Confirmed.")
        mock_tts.return_value = "ZmFrZWF1ZGlv"

        response = _post_mode(client, "casual")

    data = response.json()
    assert "confirmation_audio" in data
    assert isinstance(data["confirmation_audio"], str)


def test_mode_switch_case_insensitive(client):
    """The mode value must be lowercased/stripped before validation."""
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Done.")
        mock_tts.return_value = ""

        # Send with uppercase
        response = client.post("/mode", json={"mode": "CASUAL"})

    assert response.status_code == 200
    assert response.json()["current_mode"] == "casual"


def test_mode_switch_brain_failure_uses_fallback(client):
    """
    If brain.generate raises, the route must use a hardcoded fallback message
    and still return 200.
    """
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(side_effect=RuntimeError("LLM offline"))
        mock_tts.return_value = ""

        response = _post_mode(client, "professional")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
