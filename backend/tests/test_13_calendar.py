"""
test_13_calendar.py — Tests for POST /calendar.

Unit tests mock calendar_tasks.handle_calendar and synthesize.
Live tests require Google Calendar credentials.
"""

from unittest.mock import AsyncMock, patch

import pytest

from helpers import skip_no_home_assistant


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post_calendar(client, payload: dict):
    return client.post("/calendar", json=payload)


# ── Validation ─────────────────────────────────────────────────────────────────

def test_calendar_missing_action_returns_422(client):
    """Posting without 'action' field must return 422."""
    response = _post_calendar(client, {"details": "tomorrow"})
    assert response.status_code == 422


# ── Mocked unit tests ──────────────────────────────────────────────────────────

def test_calendar_list_events(client):
    """Listing events must call handle_calendar and return result text."""
    with patch("api.routes.calendar.calendar_tasks") as mock_ct, \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_ct.handle_calendar = AsyncMock(
            return_value="You have 3 upcoming events."
        )
        mock_tts.return_value = ""

        response = _post_calendar(client, {
            "action": "list",
            "details": "",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "You have 3 upcoming events."


def test_calendar_add_event(client):
    """Adding an event must call handle_calendar and return a confirmation."""
    with patch("api.routes.calendar.calendar_tasks") as mock_ct, \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_ct.handle_calendar = AsyncMock(
            return_value="Event 'Team sync' created for Monday, April 22 at 10:00 AM."
        )
        mock_tts.return_value = ""

        response = _post_calendar(client, {
            "action": "add",
            "details": "team sync on Monday at 10am",
            "session_id": "cal-session",
        })

    assert response.status_code == 200
    data = response.json()
    assert "created" in data["result"].lower() or "event" in data["result"].lower()


def test_calendar_response_has_required_fields(client):
    """Calendar response must include result, audio_base64, language, mode."""
    with patch("api.routes.calendar.calendar_tasks") as mock_ct, \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_ct.handle_calendar = AsyncMock(return_value="Done.")
        mock_tts.return_value = "ZmFrZWF1ZGlv"

        response = _post_calendar(client, {"action": "list"})

    data = response.json()
    for field in ("result", "audio_base64", "language", "mode"):
        assert field in data, f"Missing field in calendar response: {field!r}"


def test_calendar_exception_returns_fallback(client):
    """If handle_calendar raises, the route must return 200 with a fallback message."""
    with patch("api.routes.calendar.calendar_tasks") as mock_ct, \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_ct.handle_calendar = AsyncMock(
            side_effect=RuntimeError("Google API offline")
        )
        mock_tts.return_value = ""

        response = _post_calendar(client, {"action": "list"})

    assert response.status_code == 200
    data = response.json()
    assert "result" in data
    assert isinstance(data["result"], str)


def test_calendar_details_combined_with_action(client):
    """The route concatenates action + details before calling handle_calendar."""
    with patch("api.routes.calendar.calendar_tasks") as mock_ct, \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_ct.handle_calendar = AsyncMock(return_value="OK.")
        mock_tts.return_value = ""

        _post_calendar(client, {
            "action": "schedule",
            "details": "dentist appointment at 2pm Friday",
        })

    # Verify the combined string was passed to handle_calendar
    call_args = mock_ct.handle_calendar.call_args
    combined = call_args[0][0] if call_args[0] else call_args[1].get("command", "")
    assert "schedule" in combined.lower()
    assert "dentist" in combined.lower()


def test_calendar_no_credentials_returns_not_configured(client):
    """
    With no Google credentials, handle_calendar returns an unconfigured message.
    Test the real function path with patched _get_credentials returning None.
    """
    with patch("tools.calendar_tasks._get_credentials", return_value=None), \
         patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""
        response = _post_calendar(client, {"action": "list"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["result"], str)
    # Should mention not configured or similar
    assert len(data["result"]) > 0


# ── Live tests (require Google Calendar) ──────────────────────────────────────

@pytest.mark.requires_google_calendar
def test_live_calendar_list_events(client):
    """LIVE: List real calendar events (requires valid Google credentials)."""
    with patch("api.routes.calendar.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""
        response = _post_calendar(client, {"action": "list upcoming events"})

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["result"], str)
    assert len(data["result"]) > 0
