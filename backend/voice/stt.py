"""
voice/stt.py — Speech-to-text via faster-whisper.

Accepts audio as raw bytes or a base64 string.
Returns the transcript, detected language, and ISO 639-1 language code.
Runs entirely on CPU — no GPU required.
"""

import base64
import io
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from multilingual.language_detector import normalise_language_code, get_language_name

log = logging.getLogger(__name__)

# Whisper model size — "base" balances speed and accuracy on CPU
_MODEL_SIZE = "base"
_whisper_model = None  # loaded lazily on first use


def _get_model():
    """Lazily load the faster-whisper model (avoids import-time GPU init)."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(
                _MODEL_SIZE,
                device="cpu",
                compute_type="int8",
            )
            log.info("faster-whisper model '%s' loaded.", _MODEL_SIZE)
        except Exception as err:
            log.error("Failed to load faster-whisper: %s", err)
    return _whisper_model


@dataclass
class TranscribeResult:
    transcript: str
    language: str       # Human-readable, e.g. "English"
    language_code: str  # ISO 639-1, e.g. "en"


def transcribe_bytes(audio_bytes: bytes) -> TranscribeResult:
    """
    Transcribe raw audio bytes.

    Writes to a NamedTemporaryFile (faster-whisper needs a file path).
    The temp file is deleted immediately after transcription.
    """
    model = _get_model()
    if model is None:
        return TranscribeResult(
            transcript="",
            language="English",
            language_code="en",
        )

    if not audio_bytes:
        return TranscribeResult(transcript="", language="English", language_code="en")

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        segments, info = model.transcribe(tmp_path, beam_size=5)
        transcript = " ".join(seg.text.strip() for seg in segments).strip()

        raw_lang = info.language if hasattr(info, "language") else "en"
        lang_code = normalise_language_code(raw_lang)
        lang_name = get_language_name(lang_code)

        return TranscribeResult(
            transcript=transcript,
            language=lang_name,
            language_code=lang_code,
        )

    except Exception as err:
        log.error("Transcription failed: %s", err)
        return TranscribeResult(transcript="", language="English", language_code="en")

    finally:
        try:
            os.unlink(tmp_path)  # type: ignore[possibly-undefined]
        except Exception:
            pass


def transcribe_base64(audio_base64: str) -> TranscribeResult:
    """
    Transcribe audio provided as a base64-encoded string.
    Strips any data-URL prefix (e.g. "data:audio/webm;base64,...").
    """
    if not audio_base64:
        return TranscribeResult(transcript="", language="English", language_code="en")

    # Strip data-URL prefix if present
    if "," in audio_base64:
        audio_base64 = audio_base64.split(",", 1)[1]

    try:
        audio_bytes = base64.b64decode(audio_base64)
    except Exception as err:
        log.error("base64 decode failed: %s", err)
        return TranscribeResult(transcript="", language="English", language_code="en")

    return transcribe_bytes(audio_bytes)
