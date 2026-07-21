"""
api/routes/controls.py — POST /pause/camera  +  POST /pause/screen
"""

import logging

from fastapi import APIRouter

from api.models import PauseRequest, PauseResponse

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/pause/camera", response_model=PauseResponse)
async def pause_camera(request: PauseRequest):
    from main import app_state, save_config
    from vision.camera import camera_capture

    if request.paused:
        camera_capture.stop()
    else:
        camera_capture.start()

    active = camera_capture.is_active
    app_state["config"]["camera_active"] = active
    save_config(app_state["config"])

    return PauseResponse(active=active)


@router.post("/pause/screen", response_model=PauseResponse)
async def pause_screen(request: PauseRequest):
    from main import app_state, save_config
    from vision.screen import screen_capture

    if request.paused:
        screen_capture.stop()
    else:
        screen_capture.start()

    active = screen_capture.is_active
    app_state["config"]["screen_active"] = active
    save_config(app_state["config"])

    return PauseResponse(active=active)
