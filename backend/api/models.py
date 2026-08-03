"""
api/models.py — All Pydantic v2 request and response models.
"""

from pydantic import BaseModel, Field


# ── Shared base ───────────────────────────────────────────────────────────────

class BaseResponse(BaseModel):
    """Every API response includes these four fields."""
    response_text: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ChatResponse(BaseResponse):
    pass


# ── Voice ─────────────────────────────────────────────────────────────────────

class VoiceRequest(BaseModel):
    audio_base64: str
    session_id: str = "default"


class VoiceResponse(BaseResponse):
    transcript: str = ""


# ── Vision ────────────────────────────────────────────────────────────────────

class VisionRequest(BaseModel):
    question: str = "What do you see?"
    session_id: str = "default"


class VisionResponse(BaseModel):
    analysis: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"


# ── Mode ──────────────────────────────────────────────────────────────────────

class ModeRequest(BaseModel):
    mode: str  # "professional" | "casual"


class ModeResponse(BaseModel):
    success: bool
    current_mode: str
    confirmation_audio: str = ""


# ── Smart home ────────────────────────────────────────────────────────────────

class SmartHomeRequest(BaseModel):
    command: str
    session_id: str = "default"


class SmartHomeResponse(BaseModel):
    action_taken: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"


# ── Calendar ──────────────────────────────────────────────────────────────────

class CalendarRequest(BaseModel):
    action: str
    details: str = ""
    session_id: str = "default"


class CalendarResponse(BaseModel):
    result: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"


# ── Tasks ─────────────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    action: str
    details: str = ""
    session_id: str = "default"


class TaskResponse(BaseModel):
    result: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"


# ── Status ────────────────────────────────────────────────────────────────────

class StatusResponse(BaseModel):
    mode: str
    language: str
    camera_active: bool
    screen_active: bool
    wake_word_active: bool


# ── Controls ─────────────────────────────────────────────────────────────────

class PauseRequest(BaseModel):
    paused: bool


class PauseResponse(BaseModel):
    active: bool


# ── Weather ───────────────────────────────────────────────────────────────────

class WeatherResponse(BaseModel):
    temperature: float
    condition: str  # "sunny" | "cloudy" | "rainy" | "snowy" | "windy"
    location_name: str
    unit: str = "celsius"


# ── WebSocket streaming ───────────────────────────────────────────────────────

class WebSocketMessage(BaseModel):
    transcript: str = ""
    response_text: str = ""
    audio_base64: str = ""
    language: str = "en"
    mode: str = "professional"
