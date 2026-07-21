# FIXED: Wired wake-word activation callback to WebSocket broadcast;
#        wired camera unknown-face callback; started screen suggestion poller;
#        CORS fixed (allow_credentials=False); request logging + global exception handler.
"""
main.py — ULTRON Backend entry point.

Start with:
    python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

_CONFIG_PATH = Path(__file__).parent / "ultron_config.json"

_DEFAULT_CONFIG: dict[str, Any] = {
    "mode": "professional",
    "language": "en",
    "language_name": "English",
    "camera_active": True,
    "screen_active": True,
    "wake_word_active": True,
    "user_name": "sir",
    "session_timeout_minutes": 30,
}

app_state: dict[str, Any] = {"config": {}}


def load_config() -> dict[str, Any]:
    try:
        with open(_CONFIG_PATH) as f:
            return {**_DEFAULT_CONFIG, **json.load(f)}
    except Exception as err:
        log.warning("Could not load config (%s) — using defaults.", err)
        return dict(_DEFAULT_CONFIG)


def save_config(config: dict[str, Any]) -> None:
    try:
        with open(_CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as err:
        log.error("Could not save config: %s", err)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("ULTRON backend starting up.")

    app_state["config"] = load_config()
    cfg = app_state["config"]

    # Set memory session timeout
    from core.memory import memory
    memory._timeout = cfg.get("session_timeout_minutes", 30) * 60

    # Import the WS manager so callbacks can broadcast to all clients
    from api.websocket import manager as ws_manager

    # ── Wake word detector ────────────────────────────────────────────────────
    if cfg.get("wake_word_active", True):
        try:
            from voice.wake_word import wake_word_detector
            import asyncio

            def _on_wake_word_activation():
                """Fire a 'wake_word' event to every connected WS client."""
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        ws_manager.broadcast({"type": "wake_word"}),
                        loop,
                    )

            wake_word_detector.start(on_activation=_on_wake_word_activation)
        except Exception as err:
            log.warning("Wake word detector failed to start: %s", err)

    # ── Camera monitor ────────────────────────────────────────────────────────
    if cfg.get("camera_active", True):
        try:
            from vision.camera import camera_capture
            import asyncio

            def _on_unknown_face():
                """Alert all WS clients that an unknown face was detected."""
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        ws_manager.broadcast({
                            "type": "camera_alert",
                            "message": "Unknown person detected in camera feed.",
                        }),
                        loop,
                    )

            camera_capture.start(on_unknown_face=_on_unknown_face)
        except Exception as err:
            log.warning("Camera monitor failed to start: %s", err)

    # ── Screen monitor ────────────────────────────────────────────────────────
    if cfg.get("screen_active", True):
        try:
            from vision.screen import screen_capture
            screen_capture.start()
        except Exception as err:
            log.warning("Screen monitor failed to start: %s", err)

    # ── Start proactive suggestion background poller ───────────────────────────
    import asyncio
    from api.websocket import _poll_screen_suggestions
    asyncio.create_task(_poll_screen_suggestions())

    # ── Verify Ollama reachability ────────────────────────────────────────────
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.get(
                f"{os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}/api/tags"
            )
        log.info("Ollama connection verified.")
    except Exception:
        log.warning("Ollama not reachable on startup — will use Claude fallback.")

    log.info(
        "ULTRON is online. Mode: %s | Language: %s",
        cfg["mode"], cfg["language"],
    )

    yield

    log.info("ULTRON backend shutting down.")
    for mod_name, obj_name in [
        ("voice.wake_word", "wake_word_detector"),
        ("vision.camera",   "camera_capture"),
        ("vision.screen",   "screen_capture"),
    ]:
        try:
            mod = __import__(mod_name, fromlist=[obj_name])
            getattr(mod, obj_name).stop()
        except Exception:
            pass

    save_config(app_state["config"])
    log.info("Config saved. Goodbye.")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Ultron Backend",
    description="Personal AI assistant backend — FastAPI + Ollama + Claude",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# allow_credentials=True is INCOMPATIBLE with allow_origins=["*"] in browsers.
# Use allow_credentials=False with wildcard so all origins (including Electron
# file://) can POST freely without preflight failures.

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request logging middleware ────────────────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.body()
            log.info("→ %s %s  body: %s", request.method, request.url.path, body[:400])
        except Exception:
            pass
    response = await call_next(request)
    log.info(
        "← %s %s  status: %s",
        request.method, request.url.path, response.status_code,
    )
    return response

# ── Global exception handler ──────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    mode = app_state.get("config", {}).get("mode", "professional")
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "response_text": (
                "I encountered an internal error, sir."
                if mode == "professional"
                else "Oops, something broke on my end."
            ),
            "audio_base64": "",
            "language": "en",
            "mode": mode,
        },
    )

# ── Routers ───────────────────────────────────────────────────────────────────

from api.routes.chat import router as chat_router
from api.routes.voice import router as voice_router
from api.routes.vision import router as vision_router
from api.routes.mode import router as mode_router
from api.routes.smart_home import router as smart_home_router
from api.routes.calendar import router as calendar_router
from api.routes.status import router as status_router
from api.routes.controls import router as controls_router
from api.websocket import router as ws_router

app.include_router(chat_router)
app.include_router(voice_router)
app.include_router(vision_router)
app.include_router(mode_router)
app.include_router(smart_home_router)
app.include_router(calendar_router)
app.include_router(status_router)
app.include_router(controls_router)
app.include_router(ws_router)


@app.get("/")
async def root():
    return {"status": "online", "service": "Ultron Backend", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
