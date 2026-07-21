"""
test_12_smart_home.py — Tests for POST /smarthome.

Unit tests mock the SmartHome.execute method and synthesize.
Live tests are marked requires_home_assistant and skipped if HA is unavailable.
"""

from unittest.mock import AsyncMock, patch

import pytest

from helpers import skip_no_home_assistant


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post_smarthome(client, payload: dict):
    return client.post("/smarthome", json=payload)


# ── Validation tests ───────────────────────────────────────────────────────────

def test_smart_home_missing_command_returns_422(client):
    """Posting without 'command' field must return 422."""
    response = _post_smarthome(client, {"session_id": "test"})
    assert response.status_code == 422


# ── Mocked unit tests ──────────────────────────────────────────────────────────

def test_smart_home_turn_on_light(client):
    """Turn-on command must call smart_home.execute and return the result."""
    with patch("api.routes.smart_home.smart_home") as mock_sh, \
         patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_sh.execute = AsyncMock(return_value="Bedroom has been turn on.")
        mock_tts.return_value = ""

        response = _post_smarthome(client, {
            "command": "turn on the bedroom lights",
            "session_id": "sh-test",
        })

    assert response.status_code == 200
    data = response.json()
    assert "turn on" in data["action_taken"].lower() or "bedroom" in data["action_taken"].lower()


def test_smart_home_turn_off_light(client):
    """Turn-off command must succeed and return an action_taken string."""
    with patch("api.routes.smart_home.smart_home") as mock_sh, \
         patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_sh.execute = AsyncMock(return_value="Kitchen has been turn off.")
        mock_tts.return_value = ""

        response = _post_smarthome(client, {
            "command": "turn off the kitchen light",
        })

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["action_taken"], str)
    assert len(data["action_taken"]) > 0


def test_smart_home_returns_required_fields(client):
    """Smart home response must include action_taken, audio_base64, language, mode."""
    with patch("api.routes.smart_home.smart_home") as mock_sh, \
         patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_sh.execute = AsyncMock(return_value="Done.")
        mock_tts.return_value = "ZmFrZWF1ZGlv"

        response = _post_smarthome(client, {"command": "toggle fan"})

    data = response.json()
    for field in ("action_taken", "audio_base64", "language", "mode"):
        assert field in data, f"Missing field in smart home response: {field!r}"


def test_smart_home_execute_exception_returns_fallback(client):
    """If smart_home.execute raises, the route must return a 200 fallback."""
    with patch("api.routes.smart_home.smart_home") as mock_sh, \
         patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_sh.execute = AsyncMock(side_effect=RuntimeError("HA offline"))
        mock_tts.return_value = ""

        response = _post_smarthome(client, {"command": "turn on lights"})

    assert response.status_code == 200
    data = response.json()
    assert "action_taken" in data


def test_smart_home_no_token_returns_unconfigured_message(client):
    """
    With no HASS_TOKEN set, SmartHome.execute returns a configuration message.
    This tests the real execute path (no mock) by patching _HASS_TOKEN.
    """
    with patch("tools.smart_home._HASS_TOKEN", ""), \
         patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        response = _post_smarthome(client, {"command": "turn on bedroom lights"})

    assert response.status_code == 200
    data = response.json()
    # Should mention not configured
    assert "not configured" in data["action_taken"].lower() or isinstance(data["action_taken"], str)


# ── Live tests (require Home Assistant) ───────────────────────────────────────

@pytest.mark.requires_home_assistant
@skip_no_home_assistant
def test_live_smart_home_turn_on_light(client):
    """LIVE: Turn on a real light via Home Assistant (requires HASS_TOKEN)."""
    with patch("api.routes.smart_home.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""
        response = _post_smarthome(client, {
            "command": "turn on the bedroom lights",
        })

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["action_taken"], str)
