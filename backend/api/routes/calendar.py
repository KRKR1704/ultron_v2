"""
api/routes/calendar.py — POST /calendar  +  POST /tasks
"""

import logging

from fastapi import APIRouter

from api.models import (
    CalendarRequest, CalendarResponse,
    TaskRequest, TaskResponse,
)
from tools.calendar_tasks import calendar_tasks
from voice.tts import synthesize

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/calendar", response_model=CalendarResponse)
async def calendar(request: CalendarRequest):
    from main import app_state

    mode = app_state["config"]["mode"]
    language = app_state["config"]["language"]

    try:
        combined = f"{request.action} {request.details}".strip()
        result = await calendar_tasks.handle_calendar(combined)
        audio_b64 = await synthesize(result, language)

        return CalendarResponse(
            result=result,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/calendar error: %s", err)
        msg = "I encountered an issue with the calendar."
        return CalendarResponse(
            result=msg,
            audio_base64=await synthesize(msg, language),
            language=language,
            mode=mode,
        )


@router.post("/tasks", response_model=TaskResponse)
async def tasks(request: TaskRequest):
    from main import app_state

    mode = app_state["config"]["mode"]
    language = app_state["config"]["language"]

    try:
        combined = f"{request.action} {request.details}".strip()
        result = await calendar_tasks.handle_tasks(combined)
        audio_b64 = await synthesize(result, language)

        return TaskResponse(
            result=result,
            audio_base64=audio_b64,
            language=language,
            mode=mode,
        )

    except Exception as err:
        log.error("/tasks error: %s", err)
        msg = "I encountered an issue with the task list."
        return TaskResponse(
            result=msg,
            audio_base64=await synthesize(msg, language),
            language=language,
            mode=mode,
        )
