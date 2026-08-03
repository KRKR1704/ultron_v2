"""
api/routes/vision.py — POST /vision/camera  +  POST /vision/screen
                        GET  /vision/camera/frame  (latest raw frame for UI preview)
"""

import asyncio
import base64
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from api.models import VisionRequest, VisionResponse
from vision.camera import camera_capture
from vision.screen import screen_capture
from vision.ocr import extract_text
from vision.analyzer import analyze
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/vision/camera/frame")
async def get_camera_frame():
    """Single latest frame as base64 JSON — used for snapshots."""
    frame_b64 = camera_capture.capture_frame()
    if not frame_b64:
        return JSONResponse({"frame": None, "active": False})
    return JSONResponse({"frame": frame_b64, "active": camera_capture.is_active})


@router.get("/vision/camera/stream")
async def camera_stream():
    """
    MJPEG stream — multipart/x-mixed-replace.
    Point an <img src="…/vision/camera/stream"> at this and the browser
    renders a smooth live feed with no polling or React re-renders.
    Runs at up to 15 fps limited by the backend capture rate.
    """
    async def _generate():
        while True:
            if not camera_capture.is_active:
                # Camera paused — send a blank separator and wait
                await asyncio.sleep(0.5)
                continue

            frame_b64 = camera_capture.capture_frame()
            if frame_b64:
                frame_bytes = base64.b64decode(frame_b64)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + frame_bytes
                    + b"\r\n"
                )
            # ~15 fps
            await asyncio.sleep(1 / 15)

    return StreamingResponse(
        _generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection":    "keep-alive",
            "X-Accel-Buffering": "no",   # disable nginx buffering if present
        },
    )


@router.post("/vision/camera", response_model=VisionResponse)
async def vision_camera(request: VisionRequest):
    from main import app_state

    mode = app_state["config"]["mode"]
    language = app_state["config"]["language"]

    try:
        frame_b64 = camera_capture.capture_frame()
        if not frame_b64:
            analysis = "I was unable to access the camera."
        else:
            ocr_text = extract_text(frame_b64, language_code=language)
            analysis = await analyze(
                image_b64=frame_b64,
                question=request.question,
                context="general",
                session_id=request.session_id,
                mode=mode,
                language_code=language,
                ocr_text=ocr_text,
            )

        audio_b64 = await synthesize(analysis, language)

        return VisionResponse(
            analysis=analysis,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/vision/camera error: %s", err)
        msg = "Camera analysis failed."
        return VisionResponse(
            analysis=msg,
            audio_base64=await synthesize(msg, language),
            language=language,
            mode=mode,
        )


@router.post("/vision/screen", response_model=VisionResponse)
async def vision_screen(request: VisionRequest):
    from main import app_state

    mode = app_state["config"]["mode"]
    language = app_state["config"]["language"]

    try:
        screen_b64 = screen_capture.capture_screen()
        if not screen_b64:
            analysis = "I was unable to capture the screen."
        else:
            ocr_text = extract_text(screen_b64, language_code=language)
            context = _detect_context(ocr_text)
            analysis = await analyze(
                image_b64=screen_b64,
                question=request.question,
                context=context,
                session_id=request.session_id,
                mode=mode,
                language_code=language,
                ocr_text=ocr_text,
            )

        audio_b64 = await synthesize(analysis, language)

        return VisionResponse(
            analysis=analysis,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/vision/screen error: %s", err)
        msg = "Screen analysis failed."
        return VisionResponse(
            analysis=msg,
            audio_base64=await synthesize(msg, language),
            language=language,
            mode=mode,
        )


def _detect_context(ocr_text: str) -> str:
    """Heuristically detect screen content type from OCR output."""
    lower = ocr_text.lower()
    code_signals = [
        "def ", "import ", "function ", "const ", "var ", "class ", "return ",
        "{", "}", "//", "=>", "public ", "private ",
    ]
    if any(sig in lower for sig in code_signals):
        return "code"

    non_ascii = sum(1 for c in ocr_text if ord(c) > 127)
    if ocr_text and non_ascii / len(ocr_text) > 0.3:
        return "foreign_text"

    doc_signals = ["dear ", "sincerely", "invoice", "total", "summary", "regards"]
    if any(sig in lower for sig in doc_signals):
        return "document"

    return "general"
