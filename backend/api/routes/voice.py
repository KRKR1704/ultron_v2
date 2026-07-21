"""
api/routes/voice.py — POST /voice
Accepts either JSON { audio_base64, session_id } or multipart audio file upload.
"""

import logging

from fastapi import APIRouter, File, Form, UploadFile, Request
from fastapi.responses import JSONResponse

from api.models import VoiceRequest, VoiceResponse
from core.agent import run_agent
from voice.stt import transcribe_bytes, transcribe_base64
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/voice", response_model=VoiceResponse)
async def voice(request: Request):
    from main import app_state

    cfg = app_state["config"]
    mode = cfg.get("mode", "professional")
    config_language = cfg.get("language", "en")
    user_name = cfg.get("user_name", "sir")

    content_type = request.headers.get("content-type", "")

    # ── Parse payload ─────────────────────────────────────────────────────────
    if "multipart/form-data" in content_type:
        form = await request.form()
        audio_file: UploadFile = form.get("audio")  # type: ignore[assignment]
        session_id = form.get("session_id", "default")
        audio_bytes = await audio_file.read() if audio_file else b""
        stt_result = transcribe_bytes(audio_bytes)
    else:
        body = await request.json()
        req = VoiceRequest(**body)
        stt_result = transcribe_base64(req.audio_base64)
        session_id = req.session_id

    if not stt_result.transcript:
        fallback = "I didn't catch that. Could you try again?"
        return VoiceResponse(
            transcript="",
            response_text=fallback,
            audio_base64=await synthesize(fallback, config_language),
            language=config_language,
            mode=mode,
        )

    # Use detected language for response
    language = stt_result.language_code or config_language

    try:
        response_text = await run_agent(
            text=stt_result.transcript,
            session_id=session_id,
            mode=mode,
            language_code=language,
            user_name=user_name,
        )

        audio_b64 = await synthesize(response_text, language)

        return VoiceResponse(
            transcript=stt_result.transcript,
            response_text=response_text,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/voice error: %s", err)
        fallback = "I had trouble processing the audio. Please try again."
        return VoiceResponse(
            transcript=stt_result.transcript,
            response_text=fallback,
            audio_base64=await synthesize(fallback, language),
            language=language,
            mode=mode,
        )
