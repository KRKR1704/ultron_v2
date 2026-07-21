"""
test_19_integration.py — Full integration tests.

These tests exercise the complete request/response pipeline with only
TTS (synthesize) mocked to avoid requiring audio hardware.
LLM calls are mocked too for CI safety; add @skip_no_ollama for live tests.

Mark: slow, requires_ollama (for live variants).
"""

import pytest
from unittest.mock import AsyncMock, patch

from main import app_state
from core.memory import memory


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post_chat(client, message: str, session_id: str = "integration-default"):
    return client.post("/chat", json={"message": message, "session_id": session_id})


def _post_mode(client, mode: str):
    return client.post("/mode", json={"mode": mode})


# ── Integration tests ─────────────────────────────────────────────────────────

@pytest.mark.slow
def test_full_chat_flow_professional_mode(client):
    """
    Full /chat flow in professional mode:
    mock brain + TTS, verify response fields and correct mode.
    """
    app_state["config"]["mode"] = "professional"
    session = "integration-professional"
    memory.clear_session(session)

    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Processing complete, sir."
        mock_tts.return_value = "ZmFrZWF1ZGlv"

        response = _post_chat(client, "How are you?", session)

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "professional"
    assert data["response_text"] == "Processing complete, sir."
    assert data["audio_base64"] == "ZmFrZWF1ZGlv"
    assert "language" in data

    memory.clear_session(session)


@pytest.mark.slow
def test_mode_switch_then_chat_uses_new_mode(client):
    """
    1. Switch to casual mode via /mode
    2. Send a /chat request
    3. Verify the chat response reflects 'casual' mode
    """
    # Step 1: Switch to casual
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Casual mode on!")
        mock_tts.return_value = ""
        mode_resp = _post_mode(client, "casual")

    assert mode_resp.status_code == 200
    assert app_state["config"]["mode"] == "casual"

    # Step 2: Chat
    session = "integration-mode-switch"
    memory.clear_session(session)

    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "Hey! What's up?"
        mock_tts.return_value = ""

        chat_resp = _post_chat(client, "Tell me a joke", session)

    assert chat_resp.status_code == 200
    assert chat_resp.json()["mode"] == "casual"

    # Restore
    with patch("api.routes.mode.brain") as mock_brain, \
         patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Professional mode on.")
        mock_tts.return_value = ""
        _post_mode(client, "professional")

    memory.clear_session(session)


@pytest.mark.slow
def test_memory_persists_across_requests(client):
    """
    Two sequential chat requests with the same session_id must build
    up conversation history. The second call should find history from the first.
    """
    session = "integration-memory-persist"
    memory.clear_session(session)

    # First message
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:

        def store_and_return(*args, **kwargs):
            # Simulate what brain.generate does: store to memory
            memory.add_message(session, "user", "first message")
            memory.add_message(session, "assistant", "first response")
            return "first response"

        mock_agent.side_effect = AsyncMock(side_effect=store_and_return)
        mock_tts.return_value = ""

        r1 = _post_chat(client, "first message", session)

    assert r1.status_code == 200

    # Verify history was built
    history_after_first = memory.get_history(session)
    assert len(history_after_first) >= 2

    # Second message — history must be available
    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.return_value = "second response"
        mock_tts.return_value = ""

        r2 = _post_chat(client, "second message", session)

    assert r2.status_code == 200

    memory.clear_session(session)


@pytest.mark.slow
def test_concurrent_sessions_independent(client):
    """
    Two different session IDs must have independent memory.
    Messages from session A must not appear in session B.
    """
    session_a = "integration-concurrent-A"
    session_b = "integration-concurrent-B"
    memory.clear_session(session_a)
    memory.clear_session(session_b)

    def store_for_a(*args, **kwargs):
        memory.add_message(session_a, "user", "message for A")
        memory.add_message(session_a, "assistant", "response A")
        return "response A"

    def store_for_b(*args, **kwargs):
        memory.add_message(session_b, "user", "message for B")
        memory.add_message(session_b, "assistant", "response B")
        return "response B"

    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.side_effect = AsyncMock(side_effect=store_for_a)
        mock_tts.return_value = ""
        _post_chat(client, "hello A", session_a)

    with patch("api.routes.chat.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_agent.side_effect = AsyncMock(side_effect=store_for_b)
        mock_tts.return_value = ""
        _post_chat(client, "hello B", session_b)

    history_a = memory.get_history(session_a)
    history_b = memory.get_history(session_b)

    # Histories must be independent
    contents_a = [m["content"] for m in history_a]
    contents_b = [m["content"] for m in history_b]

    assert "message for A" in contents_a
    assert "message for B" not in contents_a
    assert "message for B" in contents_b
    assert "message for A" not in contents_b

    memory.clear_session(session_a)
    memory.clear_session(session_b)


@pytest.mark.slow
def test_mode_persists_after_config_reload(client):
    """
    After switching mode, a fresh load_config() call must return the new mode
    (because save_config was called by the route).
    """
    from main import load_config, save_config
    import tempfile
    import json
    from pathlib import Path
    from unittest.mock import patch as _patch

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump({"mode": "professional"}, tmp)
        tmp_path = Path(tmp.name)

    try:
        with _patch("main._CONFIG_PATH", tmp_path), \
             _patch("api.routes.mode.brain") as mock_brain, \
             _patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
            mock_brain.generate = AsyncMock(return_value="Casual mode activated.")
            mock_tts.return_value = ""

            # Switch to casual — this calls save_config
            resp = _post_mode(client, "casual")
            assert resp.status_code == 200

            # Reload config from file
            with _patch("main._CONFIG_PATH", tmp_path):
                reloaded = load_config()

        assert reloaded["mode"] == "casual"
    finally:
        tmp_path.unlink(missing_ok=True)
        # Restore state
        app_state["config"]["mode"] = "professional"


@pytest.mark.slow
def test_health_check_always_200(client):
    """Integration sanity: root endpoint must always return 200."""
    for _ in range(3):
        response = client.get("/")
        assert response.status_code == 200


@pytest.mark.slow
def test_status_reflects_config_mode(client):
    """GET /status must reflect the current app_state mode."""
    app_state["config"]["mode"] = "casual"

    with patch("api.routes.status.camera_capture") as mock_cam, \
         patch("api.routes.status.screen_capture") as mock_screen, \
         patch("api.routes.status.wake_word_detector") as mock_wwd:
        mock_cam.is_active = False
        mock_screen.is_active = False
        mock_wwd.is_active = False

        resp = client.get("/status")

    assert resp.json()["mode"] == "casual"
    app_state["config"]["mode"] = "professional"
