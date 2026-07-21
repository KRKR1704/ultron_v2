"""
api/routes/mode.py — POST /mode

Confirmation lines are hardcoded — no LLM call needed for a one-liner.
This makes the mode switch feel instant (TTS only, ~1 second).
"""

import logging
import random

from fastapi import APIRouter, HTTPException

from api.models import ModeRequest, ModeResponse
from core.memory import memory
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()

# In-memory cache: "text:lang" → base64 audio
# First switch synthesises and stores; every repeat is instant.
_audio_cache: dict[str, str] = {}


async def _get_confirmation_audio(text: str, language: str) -> str:
    key = f"{text}:{language}"
    if key not in _audio_cache:
        _audio_cache[key] = await synthesize(text, language)
    return _audio_cache[key]

_VALID_MODES = {"professional", "casual"}

# Pre-written in-character confirmation lines — picked randomly for variety.
# No LLM call needed: these are short, predictable, and already in character.
_PROFESSIONAL_LINES = [
    "Professional mode reactivated. Ready when you are, sir.",
    "Switching to professional mode. Standing by, sir.",
    "Professional mode engaged. How can I assist you, sir.",
    "Back to business. At your service, sir.",
]

_CASUAL_LINES = [
    "Casual mode on. What's up?",
    "Alright, keeping it relaxed. What do you need?",
    "Switching to casual. Let's make this easy.",
    "Casual mode activated. Hit me.",
]


@router.post("/mode", response_model=ModeResponse)
async def switch_mode(request: ModeRequest):
    from main import app_state, save_config

    mode = request.mode.lower().strip()
    if mode not in _VALID_MODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{mode}'. Must be 'professional' or 'casual'.",
        )

    cfg = app_state["config"]
    old_mode = cfg.get("mode", "professional")
    cfg["mode"] = mode
    save_config(cfg)

    language = cfg.get("language", "en")

    # Clear ALL session histories so old-mode tone is gone everywhere
    memory.clear_all()
    log.info("Mode switched %s → %s. All session memories cleared.", old_mode, mode)

    # Pick a random confirmation line — no LLM call, instant response
    lines = _PROFESSIONAL_LINES if mode == "professional" else _CASUAL_LINES
    confirmation_text = random.choice(lines)

    # First call synthesises; repeated switches hit the in-memory cache
    confirmation_audio = await _get_confirmation_audio(confirmation_text, language)

    return ModeResponse(
        success=True,
        current_mode=mode,
        confirmation_audio=confirmation_audio,
    )
