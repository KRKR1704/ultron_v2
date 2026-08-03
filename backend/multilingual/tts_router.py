"""
multilingual/tts_router.py — Maps a language code to the correct TTS engine + voice.

Used by voice/tts.py to decide whether to call piper or ElevenLabs.
"""

import os
from dataclasses import dataclass
from typing import Literal

TTSEngine = Literal["piper", "elevenlabs"]


@dataclass(frozen=True)
class TTSRoute:
    engine: TTSEngine
    voice: str  # piper model name OR ElevenLabs voice_id env var name


# ── Routing table ─────────────────────────────────────────────────────────────
# Piper model names must match the .onnx filename (without extension) inside
# PIPER_MODELS_PATH.  ElevenLabs entries store the *env-var name* whose value
# is the actual voice ID.

_ROUTES: dict[str, TTSRoute] = {
    "en":  TTSRoute(engine="piper",       voice="en_US-lessac-medium"),
    "hi":  TTSRoute(engine="piper",       voice="hi_IN-pratham-medium"),
    "te":  TTSRoute(engine="piper",       voice="te_IN-maya-medium"),
    "es":  TTSRoute(engine="piper",       voice="es_ES-davefx-medium"),
    "fr":  TTSRoute(engine="piper",       voice="fr_FR-siwis-medium"),
    # NOTE: "de_DE-x_low" does not exist in rhasspy/piper-voices — verified
    # against the actual repo tree (real German voices are eva_k, karlsson,
    # kerstin, mls, pavoque, ramona, thorsten, thorsten_emotional; none are
    # named "x_low"). German was out of scope for this fix pass (no model
    # downloaded/tested) — this entry is left as a KNOWN-BROKEN placeholder
    # rather than silently "fixed" without verification. Update once a real
    # de_DE voice is chosen and downloaded.
    "de":  TTSRoute(engine="piper",       voice="de_DE-x_low"),
    "ko":  TTSRoute(engine="elevenlabs",  voice="ELEVENLABS_VOICE_KO"),
    "ja":  TTSRoute(engine="elevenlabs",  voice="ELEVENLABS_VOICE_JA"),
    "zh":  TTSRoute(engine="elevenlabs",  voice="ELEVENLABS_VOICE_ZH"),
}

_DEFAULT_ROUTE = TTSRoute(engine="piper", voice="en_US-lessac-medium")


def get_tts_route(language_code: str) -> TTSRoute:
    """
    Return the TTSRoute for *language_code*.

    Accepts full BCP-47 tags — uses only the primary subtag.
    Falls back to English piper for unknown codes.
    """
    primary = language_code.lower().split("-")[0]
    return _ROUTES.get(primary, _DEFAULT_ROUTE)


def resolve_elevenlabs_voice_id(route: TTSRoute) -> str:
    """
    For an ElevenLabs route, resolve the actual voice ID from the env var.
    Returns an empty string if the env var is not set.
    """
    if route.engine != "elevenlabs":
        return ""
    return os.getenv(route.voice, "")
