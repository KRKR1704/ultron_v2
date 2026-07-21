"""
api/routes/status.py — GET /status
Polled by the frontend every 5 seconds to update the UI indicators.
"""

from fastapi import APIRouter

from api.models import StatusResponse

router = APIRouter()


@router.get("/status", response_model=StatusResponse)
async def status():
    from main import app_state
    from vision.camera import camera_capture
    from vision.screen import screen_capture
    from voice.wake_word import wake_word_detector

    cfg = app_state["config"]

    return StatusResponse(
        mode=cfg.get("mode", "professional"),
        language=cfg.get("language", "en"),
        camera_active=camera_capture.is_active,
        screen_active=screen_capture.is_active,
        wake_word_active=wake_word_detector.is_active,
    )
