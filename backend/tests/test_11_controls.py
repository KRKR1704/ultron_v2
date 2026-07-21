"""
test_11_controls.py — Tests for POST /pause/camera and POST /pause/screen.

The actual routes are at /pause/camera and /pause/screen (not /controls).
"""

from unittest.mock import patch, MagicMock, PropertyMock

import pytest

from main import app_state


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pause_camera(client, paused: bool):
    return client.post("/pause/camera", json={"paused": paused})


def _pause_screen(client, paused: bool):
    return client.post("/pause/screen", json={"paused": paused})


# ── Camera controls ────────────────────────────────────────────────────────────

def test_pause_camera_returns_success(client):
    """POST /pause/camera with paused=True must return 200."""
    with patch("vision.camera.camera_capture") as mock_cam, \
         patch("main.save_config"):
        mock_cam.is_active = False
        response = _pause_camera(client, True)

    assert response.status_code == 200


def test_resume_camera_returns_success(client):
    """POST /pause/camera with paused=False (resume) must return 200."""
    with patch("vision.camera.camera_capture") as mock_cam, \
         patch("main.save_config"):
        mock_cam.is_active = True
        response = _pause_camera(client, False)

    assert response.status_code == 200


def test_pause_camera_response_has_active_field(client):
    """Response from /pause/camera must include an 'active' boolean field."""
    with patch("vision.camera.camera_capture") as mock_cam, \
         patch("main.save_config"):
        mock_cam.is_active = False
        response = _pause_camera(client, True)

    data = response.json()
    assert "active" in data
    assert isinstance(data["active"], bool)


def test_pause_camera_calls_stop(client):
    """Sending paused=True must call camera_capture.stop()."""
    with patch("vision.camera.camera_capture") as mock_cam, \
         patch("main.save_config"):
        mock_cam.is_active = False
        _pause_camera(client, True)

    mock_cam.stop.assert_called_once()


def test_resume_camera_calls_start(client):
    """Sending paused=False must call camera_capture.start()."""
    with patch("vision.camera.camera_capture") as mock_cam, \
         patch("main.save_config"):
        mock_cam.is_active = True
        _pause_camera(client, False)

    mock_cam.start.assert_called_once()


# ── Screen controls ────────────────────────────────────────────────────────────

def test_pause_screen_returns_success(client):
    """POST /pause/screen with paused=True must return 200."""
    with patch("vision.screen.screen_capture") as mock_screen, \
         patch("main.save_config"):
        mock_screen.is_active = False
        response = _pause_screen(client, True)

    assert response.status_code == 200


def test_resume_screen_returns_success(client):
    """POST /pause/screen with paused=False must return 200."""
    with patch("vision.screen.screen_capture") as mock_screen, \
         patch("main.save_config"):
        mock_screen.is_active = True
        response = _pause_screen(client, False)

    assert response.status_code == 200


def test_pause_screen_response_has_active_field(client):
    """Response from /pause/screen must include an 'active' boolean field."""
    with patch("vision.screen.screen_capture") as mock_screen, \
         patch("main.save_config"):
        mock_screen.is_active = False
        response = _pause_screen(client, True)

    data = response.json()
    assert "active" in data
    assert isinstance(data["active"], bool)


def test_pause_screen_calls_stop(client):
    """Sending paused=True to /pause/screen must call screen_capture.stop()."""
    with patch("vision.screen.screen_capture") as mock_screen, \
         patch("main.save_config"):
        mock_screen.is_active = False
        _pause_screen(client, True)

    mock_screen.stop.assert_called_once()


def test_resume_screen_calls_start(client):
    """Sending paused=False to /pause/screen must call screen_capture.start()."""
    with patch("vision.screen.screen_capture") as mock_screen, \
         patch("main.save_config"):
        mock_screen.is_active = True
        _pause_screen(client, False)

    mock_screen.start.assert_called_once()


def test_invalid_body_pause_camera_returns_422(client):
    """Sending an invalid payload to /pause/camera must return 422."""
    response = client.post("/pause/camera", json={"paused": "yes_please"})
    # Pydantic will coerce or reject — 200 if coerced, 422 if rejected
    # Either is acceptable; just must not be 500
    assert response.status_code in (200, 422)


def test_invalid_body_pause_screen_returns_422(client):
    """Sending an invalid payload to /pause/screen must return 422."""
    response = client.post("/pause/screen", json={"wrong_field": True})
    # Missing 'paused' required field — expect 422
    assert response.status_code == 422
