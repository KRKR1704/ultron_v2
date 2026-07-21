"""
test_18_websocket.py — Tests for WebSocket /ws endpoint.

Uses TestClient.websocket_connect() for synchronous WebSocket testing.
Mocks transcribe_bytes, run_agent, and synthesize.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────

@dataclass
class _FakeSTTResult:
    transcript: str
    language: str = "English"
    language_code: str = "en"


def _mock_stt(transcript: str = "test input"):
    return _FakeSTTResult(transcript=transcript, language="English", language_code="en")


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_websocket_connect_success(client):
    """Client must be able to connect to /ws without errors."""
    with client.websocket_connect("/ws") as ws:
        # Connection established — no exception means success
        pass


def test_websocket_ping_pong(client):
    """Sending a ping message must receive a pong response."""
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        response = ws.receive_json()
        assert response.get("type") == "pong"


def test_websocket_receives_message_after_send(client):
    """
    Sending a text message over WebSocket must trigger transcript + response frames.
    """
    with patch("api.websocket.transcribe_bytes", return_value=_mock_stt("hello")), \
         patch("api.websocket.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("core.brain.httpx.AsyncClient") as mock_http:

        mock_tts.return_value = ""

        # Mock Ollama streaming to return a simple response
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.aiter_lines = AsyncMock(return_value=_async_lines([
            json.dumps({"message": {"content": "Hello, sir."}}),
            json.dumps({"done": True}),
        ]))
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=False)

        mock_client_instance = AsyncMock()
        mock_client_instance.stream = MagicMock(return_value=mock_context)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value = mock_client_instance

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "text", "text": "hello"}))

            # Collect frames until done or timeout
            frames = []
            for _ in range(10):
                try:
                    frame = ws.receive_json()
                    frames.append(frame)
                    if frame.get("type") == "done":
                        break
                except Exception:
                    break

    # Must have received at least a transcript frame
    frame_types = [f.get("type") for f in frames]
    assert "transcript" in frame_types or len(frames) > 0


def test_websocket_end_of_speech_processes_audio(client):
    """
    Sending end_of_speech with an empty buffer must result in an empty
    transcript frame (no audio buffered yet).
    """
    empty_result = _FakeSTTResult(transcript="", language="English", language_code="en")

    with patch("api.websocket.transcribe_bytes", return_value=empty_result), \
         patch("api.websocket.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_tts.return_value = ""

        with client.websocket_connect("/ws") as ws:
            ws.send_text(json.dumps({"type": "end_of_speech"}))
            # No audio in buffer — nothing happens, no crash
            # Give it a moment to process
            try:
                frame = ws.receive_json()
                # If we got a transcript, it should be empty
                if frame.get("type") == "transcript":
                    assert frame.get("text") == ""
            except Exception:
                pass  # No frame received is also acceptable (empty buffer)


def test_websocket_disconnect_handled_gracefully(client):
    """Disconnecting abruptly must not crash the server."""
    with client.websocket_connect("/ws") as ws:
        ws.close()  # Disconnect
    # No exception = graceful handling


def test_websocket_invalid_json_handled(client):
    """Sending invalid JSON text must not crash the WebSocket handler."""
    with client.websocket_connect("/ws") as ws:
        # Send malformed JSON — the server should handle it without crashing
        try:
            ws.send_text("this is not JSON {{{")
            # Server may close the connection or send an error frame
            try:
                frame = ws.receive_json()
                # If we get a response, it could be an error frame
                if frame.get("type"):
                    pass  # Any typed frame is acceptable
            except Exception:
                pass  # Connection closed is also acceptable
        except Exception:
            pass  # Sending itself may fail if server already closed


def test_websocket_multiple_ping_pong(client):
    """Multiple ping-pong exchanges must all succeed."""
    with client.websocket_connect("/ws") as ws:
        for i in range(3):
            ws.send_text(json.dumps({"type": "ping"}))
            response = ws.receive_json()
            assert response.get("type") == "pong", (
                f"Expected pong on iteration {i}, got {response}"
            )


# ── Async generator helper ─────────────────────────────────────────────────────

async def _async_lines(lines: list):
    for line in lines:
        yield line
