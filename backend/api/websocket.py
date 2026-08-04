# FIXED: Added ConnectionManager for multi-client broadcasting; proactive screen
#        suggestions now polled and pushed to all connected clients; wake-word
#        activation signal forwarded to all clients; unknown-face alert supported;
#        wake-word follow-up command (listen -> understand -> respond) wired to
#        the same STT -> agent -> TTS pipeline /voice already uses.
"""
api/websocket.py — WS /ws — Real-time voice streaming & event broadcast.

Receives raw audio chunks from the frontend.
Streams back JSON frames:
  { "type": "transcript",   "text": str }
  { "type": "token",        "text": str }
  { "type": "audio_generating" }
  { "type": "audio",        "audio_base64": str }
  { "type": "done",         "language": str, "mode": str }
  { "type": "wake_word" }                         ← wake word activated
  { "type": "suggestion",   "text": str }         ← proactive screen hint
  { "type": "camera_alert", "message": str }      ← unknown face detected
  { "type": "ping" / "pong" }
  { "type": "error",        "message": str }

process_wake_word_command() (below) broadcasts the transcript/token/
audio_generating/audio/done sequence too — same frame vocabulary as the
per-connection _process_audio() below, just via manager.broadcast() to
every connected client instead of one, since the wake word detector isn't
tied to any specific WebSocket connection.
"""

import asyncio
import json
import logging
from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from voice.stt import transcribe_bytes
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()

_MAX_CHUNK_BYTES = 1_024 * 1_024  # 1 MB audio buffer
_WAKE_WORD_SESSION_ID = "wake-word-session"


# ── Connection manager ────────────────────────────────────────────────────────

class ConnectionManager:
    """Tracks all active WebSocket connections and lets the app broadcast to all."""

    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        log.info("WS client connected. Total: %d", len(self._connections))

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
            self._connections.remove(ws)
        log.info("WS client disconnected. Total: %d", len(self._connections))

    async def broadcast(self, message: dict) -> None:
        """Send a JSON message to every connected client. Dead connections are pruned."""
        dead: List[WebSocket] = []
        for ws in list(self._connections):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    @property
    def has_clients(self) -> bool:
        return len(self._connections) > 0


# Module-level singleton — imported by main.py to wire callbacks
manager = ConnectionManager()


# ── Background suggestion poller ──────────────────────────────────────────────

async def _poll_screen_suggestions() -> None:
    """
    Background task: poll screen_capture.suggestion_queue every 30 seconds
    and broadcast any pending proactive suggestions to all WS clients.
    """
    while True:
        await asyncio.sleep(30)
        try:
            from vision.screen import screen_capture
            while True:
                suggestion = screen_capture.pop_suggestion()
                if suggestion is None:
                    break
                if manager.has_clients:
                    await manager.broadcast({"type": "suggestion", "text": suggestion})
                    log.info("Broadcasted proactive suggestion: %s", suggestion[:60])
        except Exception as err:
            log.debug("Suggestion poller error: %s", err)


# ── Wake-word follow-up command processing ─────────────────────────────────────

async def process_wake_word_command(audio_wav_bytes: bytes) -> None:
    """
    Handle the follow-up command captured after a wake-word activation
    (voice/wake_word.py's on_command_captured callback, wired up in
    main.py's lifespan). Runs the SAME STT -> agent -> TTS pipeline
    POST /voice uses (api.routes.voice.run_stt_agent_tts) rather than a
    parallel implementation, and broadcasts the same frame types
    _process_audio() below already sends per-connection — just to every
    connected client instead of one, since this isn't tied to a specific
    WebSocket.

    Always resumes the wake word detector's passive "ultron" listening in
    a finally block, success or failure, so a single bad turn (STT error,
    agent exception, TTS failure) can never leave the detector stuck.
    """
    from main import app_state
    from api.routes.voice import run_stt_agent_tts
    from voice.wake_word import wake_word_detector

    try:
        cfg = app_state["config"]
        mode = cfg.get("mode", "professional")
        language = cfg.get("language", "en")
        user_name = cfg.get("user_name", "sir")

        stt_result = transcribe_bytes(audio_wav_bytes)
        await manager.broadcast({"type": "transcript", "text": stt_result.transcript})

        # run_stt_agent_tts already handles an empty transcript gracefully
        # (returns "I didn't catch that..." without calling the agent) —
        # reused as-is, so silence/noise after "ultron" can never reach
        # the agent and get hallucinated into a fake answer.
        result = await run_stt_agent_tts(stt_result, _WAKE_WORD_SESSION_ID, mode, language, user_name)

        await manager.broadcast({"type": "token", "text": result.response_text})
        await manager.broadcast({"type": "audio_generating"})
        await manager.broadcast({"type": "audio", "audio_base64": result.audio_base64})
        await manager.broadcast({"type": "done", "language": result.language, "mode": result.mode})

    except Exception as err:
        log.error("process_wake_word_command error: %s", err)
        await manager.broadcast({"type": "error", "message": "Wake word command processing failed."})

    finally:
        wake_word_detector.resume_passive_listening()


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    audio_buffer = bytearray()

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive(), timeout=60.0)
            except asyncio.TimeoutError:
                await ws.send_json({"type": "ping"})
                continue

            # ws.receive() is the low-level ASGI call — it does NOT raise
            # WebSocketDisconnect itself (that's only auto-raised by the
            # high-level receive_text()/receive_json()/receive_bytes()
            # helpers). On client disconnect it returns a plain
            # {"type": "websocket.disconnect", ...} message once; calling
            # receive() again afterward raises RuntimeError('Cannot call
            # "receive" once a disconnect message has been received.').
            # Neither branch below matches that dict (no "bytes"/"text"
            # key), so without this check the loop would silently call
            # receive() again next iteration and hit that RuntimeError.
            if data.get("type") == "websocket.disconnect":
                break

            if "bytes" in data and data["bytes"]:
                chunk = data["bytes"]
                audio_buffer.extend(chunk)

                if len(audio_buffer) >= _MAX_CHUNK_BYTES:
                    await _process_audio(ws, bytes(audio_buffer))
                    audio_buffer.clear()

            elif "text" in data:
                msg = json.loads(data["text"])
                msg_type = msg.get("type", "")

                if msg_type == "end_of_speech":
                    if audio_buffer:
                        await _process_audio(ws, bytes(audio_buffer))
                        audio_buffer.clear()

                elif msg_type == "text":
                    await _process_text(ws, msg.get("text", ""), msg.get("session_id", "ws-session"))

                elif msg_type == "ping":
                    await ws.send_json({"type": "pong"})

    except WebSocketDisconnect as err:
        log.info("WebSocket client disconnected (code=%s).", err.code)
    except Exception as err:
        log.error("WebSocket error: %s", err)
        try:
            await ws.send_json({"type": "error", "message": str(err)})
        except Exception:
            pass
    finally:
        manager.disconnect(ws)


# ── Audio processing ──────────────────────────────────────────────────────────

async def _process_audio(ws: WebSocket, audio_bytes: bytes) -> None:
    """Transcribe audio bytes then stream the response back."""
    from main import app_state

    cfg = app_state["config"]
    mode = cfg.get("mode", "professional")
    language = cfg.get("language", "en")
    user_name = cfg.get("user_name", "sir")

    try:
        stt_result = transcribe_bytes(audio_bytes)
        transcript = stt_result.transcript.strip()

        if not transcript:
            await ws.send_json({"type": "transcript", "text": ""})
            return

        detected_lang = stt_result.language_code or language
        await ws.send_json({"type": "transcript", "text": transcript})

        response_text = await _stream_response(ws, transcript, mode, detected_lang, user_name=user_name)

        await ws.send_json({"type": "audio_generating"})
        audio_b64 = await synthesize(response_text, detected_lang)
        await ws.send_json({"type": "audio", "audio_base64": audio_b64})
        await ws.send_json({"type": "done", "language": detected_lang, "mode": mode})

    except Exception as err:
        log.error("_process_audio error: %s", err)
        await ws.send_json({"type": "error", "message": "Audio processing failed."})


async def _process_text(ws: WebSocket, text: str, session_id: str = "ws-session") -> None:
    """Process a plain text message over the WebSocket."""
    from main import app_state
    from multilingual.language_detector import detect_language_from_text

    cfg = app_state["config"]
    mode = cfg.get("mode", "professional")
    user_name = cfg.get("user_name", "sir")

    # Detect language from text — session-aware (see multilingual/language_detector.py)
    language = detect_language_from_text(text, session_id=session_id)

    try:
        await ws.send_json({"type": "transcript", "text": text})
        response_text = await _stream_response(ws, text, mode, language, session_id=session_id, user_name=user_name)
        audio_b64 = await synthesize(response_text, language)
        await ws.send_json({"type": "audio", "audio_base64": audio_b64})
        await ws.send_json({"type": "done", "language": language, "mode": mode})

    except Exception as err:
        log.error("_process_text error: %s", err)
        await ws.send_json({"type": "error", "message": "Text processing failed."})


async def _stream_response(
    ws: WebSocket,
    text: str,
    mode: str,
    language_code: str,
    session_id: str = "ws-session",
    user_name: str = "sir",
) -> str:
    """
    Run the agent and stream response tokens back over the WebSocket.
    Returns the full response text.

    - Tool intents: run agent fully, emit as single token block.
    - direct_answer: attempt Ollama streaming; Claude fallback chunks by word.
    """
    import httpx
    import os
    from core.memory import memory
    from core.prompt_manager import build_system_prompt
    from core.agent import classify_intent, run_agent

    system_prompt = build_system_prompt(mode, language_code, user_name=user_name)

    intent = classify_intent(text)
    if intent != "direct_answer":
        full_response = await run_agent(text, session_id, mode, language_code, user_name=user_name)
        await ws.send_json({"type": "token", "text": full_response})
        return full_response

    # direct_answer — try Ollama streaming
    history = memory.get_history(session_id)
    messages = (
        [{"role": "system", "content": system_prompt}]
        + history
        + [{"role": "user", "content": text}]
    )

    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    full_response = ""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                f"{ollama_base}/api/chat",
                json={
                    "model": os.getenv("OLLAMA_MODEL", "llama3"),
                    "messages": messages,
                    "stream": True,
                },
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            full_response += token
                            await ws.send_json({"type": "token", "text": token})
                    except json.JSONDecodeError:
                        continue

    except Exception as ollama_err:
        log.warning("Ollama streaming failed (%s), using Claude.", ollama_err)
        from core.brain import brain
        full_response = await brain.generate(
            prompt=text,
            session_id=session_id,
            mode=mode,
            language_code=language_code,
            user_name=user_name,
        )
        words = full_response.split()
        for i in range(0, len(words), 3):
            chunk = " ".join(words[i : i + 3]) + " "
            await ws.send_json({"type": "token", "text": chunk})
            await asyncio.sleep(0.05)

    if full_response:
        memory.add_message(session_id, "user", text)
        memory.add_message(session_id, "assistant", full_response)

    return full_response
