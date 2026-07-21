"""
test_10_status.py — Tests for GET /status.

The status route imports camera_capture, screen_capture, and wake_word_detector
from within the handler body (lazy imports). We patch the originating module
singletons so the handler picks up our mocks.
"""

import time
from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from main import app_state


# ── Patch context helper ──────────────────────────────────────────────────────

def _status_mocks(cam_active=False, screen_active=False, wwd_active=False):
    """Return a stacked context manager patching all three hardware singletons."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("vision.camera.camera_capture") as mock_cam, \
             patch("vision.screen.screen_capture") as mock_screen, \
             patch("voice.wake_word.wake_word_detector") as mock_wwd:
            mock_cam.is_active = cam_active
            mock_screen.is_active = screen_active
            mock_wwd.is_active = wwd_active
            yield mock_cam, mock_screen, mock_wwd

    return _ctx()


def _get_status(client):
    return client.get("/status")


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_status_returns_200(client):
    """GET /status must return HTTP 200."""
    with _status_mocks():
        response = _get_status(client)
    assert response.status_code == 200


def test_status_has_mode_field(client):
    """Response must include a 'mode' string field."""
    with _status_mocks():
        response = _get_status(client)
    data = response.json()
    assert "mode" in data
    assert isinstance(data["mode"], str)
    assert data["mode"] in ("professional", "casual")


def test_status_has_language_field(client):
    """Response must include a 'language' string field."""
    with _status_mocks():
        response = _get_status(client)
    data = response.json()
    assert "language" in data
    assert isinstance(data["language"], str)


def test_status_has_camera_active_field(client):
    """Response must include a boolean 'camera_active' field."""
    with _status_mocks(cam_active=True):
        response = _get_status(client)
    data = response.json()
    assert "camera_active" in data
    assert isinstance(data["camera_active"], bool)


def test_status_has_screen_active_field(client):
    """Response must include a boolean 'screen_active' field."""
    with _status_mocks(screen_active=True):
        response = _get_status(client)
    data = response.json()
    assert "screen_active" in data
    assert isinstance(data["screen_active"], bool)


def test_status_has_wake_word_active_field(client):
    """Response must include a boolean 'wake_word_active' field."""
    with _status_mocks(wwd_active=True):
        response = _get_status(client)
    data = response.json()
    assert "wake_word_active" in data
    assert isinstance(data["wake_word_active"], bool)


def test_status_reflects_current_mode(client):
    """status.mode must match app_state['config']['mode']."""
    app_state["config"]["mode"] = "casual"

    with _status_mocks():
        response = _get_status(client)

    data = response.json()
    assert data["mode"] == "casual"

    # Restore
    app_state["config"]["mode"] = "professional"


def test_status_camera_active_true_when_running(client):
    """camera_active must be True when the camera mock reports is_active=True."""
    with _status_mocks(cam_active=True, screen_active=False, wwd_active=False):
        response = _get_status(client)
    data = response.json()
    assert data["camera_active"] is True


def test_status_camera_active_false_when_stopped(client):
    """camera_active must be False when the camera mock reports is_active=False."""
    with _status_mocks(cam_active=False):
        response = _get_status(client)
    data = response.json()
    assert data["camera_active"] is False


def test_status_uptime_is_non_negative_number(client):
    """
    The status endpoint does not expose 'uptime' in the current schema,
    but all numeric fields (if any) must be non-negative.
    This also confirms the endpoint is generally healthy.
    """
    with _status_mocks():
        response = _get_status(client)

    assert response.status_code == 200
    data = response.json()
    for key, value in data.items():
        if isinstance(value, (int, float)):
            assert value >= 0, f"Numeric field {key!r} is negative: {value}"
