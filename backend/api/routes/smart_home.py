"""
api/routes/smart_home.py — POST /smarthome
"""

import logging

from fastapi import APIRouter

from api.models import SmartHomeRequest, SmartHomeResponse
from tools.smart_home import smart_home
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/smarthome", response_model=SmartHomeResponse)
async def smarthome(request: SmartHomeRequest):
    from main import app_state

    mode = app_state["config"]["mode"]
    language = app_state["config"]["language"]

    try:
        action_taken = await smart_home.execute(request.command)
        audio_b64 = await synthesize(action_taken, language)

        return SmartHomeResponse(
            action_taken=action_taken,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/smarthome error: %s", err)
        msg = "Smart home command failed. Please check your Home Assistant setup."
        return SmartHomeResponse(
            action_taken=msg,
            audio_base64=await synthesize(msg, language),
            language=language,
            mode=mode,
        )
