"""
test_09_vision.py — Tests for POST /vision/camera and POST /vision/screen.

Mocks camera_capture, screen_capture, OCR, and the analyzer so no real
hardware or LLM calls are made.
"""

from unittest.mock import AsyncMock, patch, MagicMock

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post_vision_camera(client, payload: dict):
    return client.post("/vision/camera", json=payload)


def _post_vision_screen(client, payload: dict):
    return client.post("/vision/screen", json=payload)


# ── camera tests ───────────────────────────────────────────────────────────────

def test_vision_missing_image_camera_uses_defaults(client):
    """
    VisionRequest has all optional fields — a completely empty body still works
    (question defaults to 'What do you see?', session_id defaults to 'default').
    """
    with patch("api.routes.vision.camera_capture") as mock_cam, \
         patch("api.routes.vision.extract_text", return_value=""), \
         patch("api.routes.vision.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_cam.capture_frame.return_value = "ZmFrZWltYWdl"  # fake base64
        mock_analyze.return_value = "I see a desk."
        mock_tts.return_value = ""

        response = _post_vision_camera(client, {})

    assert response.status_code == 200


def test_vision_camera_with_valid_image_returns_description(client, test_image_base64):
    """Camera vision endpoint must return an analysis string."""
    with patch("api.routes.vision.camera_capture") as mock_cam, \
         patch("api.routes.vision.extract_text", return_value="some text"), \
         patch("api.routes.vision.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_cam.capture_frame.return_value = test_image_base64
        mock_analyze.return_value = "I see a white pixel."
        mock_tts.return_value = ""

        response = _post_vision_camera(client, {
            "question": "What do you see?",
            "session_id": "vision-test",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["analysis"] == "I see a white pixel."


def test_vision_camera_response_has_required_fields(client):
    """Camera vision response must include analysis, audio_base64, language, mode."""
    with patch("api.routes.vision.camera_capture") as mock_cam, \
         patch("api.routes.vision.extract_text", return_value=""), \
         patch("api.routes.vision.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_cam.capture_frame.return_value = "ZmFrZQ=="
        mock_analyze.return_value = "A blank wall."
        mock_tts.return_value = ""

        response = _post_vision_camera(client, {"question": "what is this"})

    data = response.json()
    for field in ("analysis", "audio_base64", "language", "mode"):
        assert field in data, f"Missing field: {field!r}"


def test_vision_camera_no_frame_returns_fallback(client):
    """If the camera returns no frame, the response must contain a fallback message."""
    with patch("api.routes.vision.camera_capture") as mock_cam, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_cam.capture_frame.return_value = None  # no frame
        mock_tts.return_value = ""

        response = _post_vision_camera(client, {"question": "what's there"})

    assert response.status_code == 200
    data = response.json()
    assert "camera" in data["analysis"].lower() or "unable" in data["analysis"].lower()


def test_vision_camera_exception_returns_error_message(client):
    """If the camera raises, the route must catch it and return a 200 with error text."""
    with patch("api.routes.vision.camera_capture") as mock_cam, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_cam.capture_frame.side_effect = RuntimeError("hardware failure")
        mock_tts.return_value = ""

        response = _post_vision_camera(client, {"question": "what is this"})

    assert response.status_code == 200
    data = response.json()
    assert "analysis" in data


# ── screen tests ───────────────────────────────────────────────────────────────

def test_vision_screen_with_valid_capture_returns_description(client):
    """Screen vision endpoint must return an analysis string from the mocked analyzer."""
    with patch("api.routes.vision.screen_capture") as mock_screen, \
         patch("api.routes.vision.extract_text", return_value="import os"), \
         patch("api.routes.vision.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_screen.capture_screen.return_value = "ZmFrZXNjcmVlbg=="
        mock_analyze.return_value = "I see Python code."
        mock_tts.return_value = ""

        response = _post_vision_screen(client, {
            "question": "What am I looking at?",
            "session_id": "screen-test",
        })

    assert response.status_code == 200
    data = response.json()
    assert data["analysis"] == "I see Python code."


def test_vision_screen_response_has_required_fields(client):
    """Screen vision response must include analysis, audio_base64, language, mode."""
    with patch("api.routes.vision.screen_capture") as mock_screen, \
         patch("api.routes.vision.extract_text", return_value=""), \
         patch("api.routes.vision.analyze", new_callable=AsyncMock) as mock_analyze, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_screen.capture_screen.return_value = "ZmFrZQ=="
        mock_analyze.return_value = "A desktop."
        mock_tts.return_value = ""

        response = _post_vision_screen(client, {})

    data = response.json()
    for field in ("analysis", "audio_base64", "language", "mode"):
        assert field in data, f"Missing field: {field!r}"


def test_vision_screen_no_capture_returns_fallback(client):
    """If screen_capture returns None, the response must contain a fallback."""
    with patch("api.routes.vision.screen_capture") as mock_screen, \
         patch("api.routes.vision.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_screen.capture_screen.return_value = None
        mock_tts.return_value = ""

        response = _post_vision_screen(client, {})

    assert response.status_code == 200
    data = response.json()
    assert "screen" in data["analysis"].lower() or "unable" in data["analysis"].lower()
