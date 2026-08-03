# FIXED: Added text-based language detection; expanded multilingual mode-switch
#        patterns; mode is read fresh from app_state on every request;
#        detailed parse-error logging; session_id always used.
"""
api/routes/chat.py — POST /chat

Accepts { message: str, session_id: str } and returns:
  { response_text, audio_base64, language, mode }

The endpoint:
  1. Detects the input language (via langdetect) so TTS/LLM use the right language.
  2. Detects mode-switch intent in ANY language via keyword patterns + LLM fallback.
  3. Updates config and responds already in the new mode's tone.
"""

import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from api.models import ChatRequest, ChatResponse
from core.agent import run_agent
from core.memory import memory
from multilingual.language_detector import detect_language_from_text
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()

# ── Mode-switch detection patterns ────────────────────────────────────────────
# English patterns + common transliterations/keywords used across languages.
# Covers: casual switch, professional switch, in English and loose keywords.

_MODE_SWITCH_PATTERNS: list[tuple[str, str]] = [
    # → casual (English)
    (r"\b(switch|change|go|put|set)\s+(to\s+)?(casual|chill|relax(ed)?|friendly|informal)\b", "casual"),
    (r"\bcasual\s*(mode)?\b", "casual"),
    (r"\brelax\s*(mode)?\b", "casual"),
    (r"\bchill\s*(mode|out)?\b", "casual"),
    (r"\bbe\s+(more\s+)?(casual|chill|friendly|relaxed|cool|fun)\b", "casual"),
    (r"\bstop\s+being\s+(so\s+)?(formal|stiff|professional|serious)\b", "casual"),
    (r"\bgo\s+(casual|informal|easy|fun)\b", "casual"),
    (r"\bfriendly\s+mode\b", "casual"),
    (r"\binformal\s+mode\b", "casual"),
    # → professional (English)
    (r"\b(switch|change|go|put|set)\s+(to\s+)?(professional|pro|formal|business|strict|serious)\b", "professional"),
    (r"\bprofessional\s*(mode)?\b", "professional"),
    (r"\bbusiness\s*(mode)?\b", "professional"),
    (r"\bformal\s*(mode)?\b", "professional"),
    (r"\bbe\s+(more\s+)?(professional|formal|serious|strict)\b", "professional"),
    (r"\bback\s+to\s+(professional|formal|pro|business|strict)\b", "professional"),
    (r"\bpro\s+mode\b", "professional"),
    # Multilingual keywords (transliteration / loan words common across languages)
    # Hindi/Telugu/South Asian languages
    (r"\bkasual\b", "casual"),
    (r"\bprofessional\s+mode\b", "professional"),
    # Japanese (romaji)
    (r"\bkajuaru\b", "casual"),
    (r"\bpurof[ei]ssel?n?aru?\b", "professional"),
    # Korean (romaji)
    (r"\bkajeual\b", "casual"),
    # Chinese (romaji)
    (r"\bsuíbiàn\b", "casual"),
    (r"\bzhuānyè\b", "professional"),
    # Spanish
    (r"\b(modo\s+)?(informal|relajado|casual)\b", "casual"),
    (r"\b(modo\s+)?(profesional|formal|serio)\b", "professional"),
    # French
    (r"\b(mode\s+)?(décontracté|informel|casual)\b", "casual"),
    (r"\b(mode\s+)?(professionnel|formel|sérieux)\b", "professional"),
    # German
    (r"\b(modus\s+)?(locker|lässig|casual|freundlich)\b", "casual"),
    (r"\b(modus\s+)?(professionell|formell|ernst)\b", "professional"),
    # Arabic
    (r"\bغير\s+رسمي\b", "casual"),
    (r"\bرسمي\b", "professional"),
]

_MODE_CONFIRM: dict[str, str] = {
    "professional": (
        "Professional mode reactivated. All systems calibrated for maximum efficiency, sir."
    ),
    "casual": (
        "Casual mode on — I'll lighten up. What's on your mind?"
    ),
}


def _detect_mode_switch(text: str) -> str | None:
    """Return the new mode string if *text* is a mode-switch command, else None."""
    lower = text.lower()
    for pattern, mode in _MODE_SWITCH_PATTERNS:
        if re.search(pattern, lower):
            return mode
    return None


@router.post("/chat", response_model=ChatResponse)
async def chat(request: Request):
    """
    Accept { message: str, session_id: str } — return ChatResponse.

    Taking the raw Request lets us log body on validation errors.
    """
    from main import app_state, save_config

    # ── Parse + validate ──────────────────────────────────────────────────────
    try:
        body = await request.json()
        log.info("/chat body: %s", str(body)[:400])
        req = ChatRequest(**body)
    except Exception as parse_err:
        raw = await request.body()
        log.error("/chat parse error — raw body: %s | error: %s", raw[:500], parse_err)
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(parse_err),
                "hint": 'Expected JSON body: {"message": string, "session_id": string}',
                "received": str(raw[:500]),
            },
        )

    # ── Read config fresh on every request ────────────────────────────────────
    cfg = app_state["config"]
    mode = cfg.get("mode", "professional")
    user_name = cfg.get("user_name", "sir")

    # ── Detect language from input text ───────────────────────────────────────
    # Session-aware: short/low-confidence messages inherit this session's
    # last-known language instead of a fresh (and often wrong) guess.
    language = detect_language_from_text(req.message, session_id=req.session_id)

    # ── Mode-switch detection ─────────────────────────────────────────────────
    new_mode = _detect_mode_switch(req.message)
    mode_switched = False

    if new_mode and new_mode != mode:
        mode = new_mode
        cfg["mode"] = mode
        save_config(cfg)
        mode_switched = True

        # Clear conversation history so old-mode tone doesn't bleed through
        memory.clear_session(req.session_id)
        log.info(
            "Mode switched to '%s' via chat — session memory cleared for %s",
            mode,
            req.session_id,
        )

    # ── Short mode-switch message → direct confirmation (skip agent) ──────────
    if mode_switched and len(req.message.split()) <= 8:
        confirmation = _MODE_CONFIRM[mode]
        audio_b64 = await synthesize(confirmation, language)
        return ChatResponse(
            response_text=confirmation,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    # ── Normal agent flow ─────────────────────────────────────────────────────
    try:
        response_text = await run_agent(
            text=req.message,
            session_id=req.session_id,
            mode=mode,
            language_code=language,
            user_name=user_name,
        )

        audio_b64 = await synthesize(response_text, language)

        return ChatResponse(
            response_text=response_text,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/chat agent error: %s", err, exc_info=True)
        if mode == "professional":
            fallback = "I encountered an error processing that request, sir."
        else:
            fallback = "Oops, something went wrong on my end. Try again?"
        return ChatResponse(
            response_text=fallback,
            audio_base64=await synthesize(fallback, language),
            language=language,
            mode=mode,
        )
