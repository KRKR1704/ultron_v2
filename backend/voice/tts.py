"""
voice/tts.py — Text-to-speech router.

Routes synthesis to piper-tts or ElevenLabs depending on language code.
Always returns audio as a base64-encoded string — never writes to disk.
"""

import base64
import io
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from multilingual.tts_router import get_tts_route, resolve_elevenlabs_voice_id

load_dotenv()
log = logging.getLogger(__name__)

_PIPER_MODELS_PATH  = Path(os.getenv("PIPER_MODELS_PATH", "./piper_models"))
_ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

# Fallback used only if a voice's .onnx.json is missing/malformed — every
# voice model actually shipped in piper_models/ today declares its own real
# rate (see _get_sample_rate()), so this default should rarely, if ever, fire.
_DEFAULT_SAMPLE_RATE = 22050

# Resolved once at first use — never search PATH repeatedly
_piper_cmd_cache: Optional[str] = None


def _resolve_piper_cmd() -> Optional[str]:
    """Find the piper executable once and cache the result."""
    global _piper_cmd_cache
    if _piper_cmd_cache is not None:
        return _piper_cmd_cache

    import platform
    candidates = [
        str(_PIPER_MODELS_PATH / ("piper.exe" if platform.system() == "Windows" else "piper")),
        "piper.exe" if platform.system() == "Windows" else "piper",
        "piper",
    ]
    for candidate in candidates:
        try:
            subprocess.run([candidate, "--help"], capture_output=True, timeout=5)
            _piper_cmd_cache = candidate
            log.info("Piper executable resolved: %s", candidate)
            return _piper_cmd_cache
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    log.error(
        "piper executable not found in %s or PATH. "
        "Download from https://github.com/rhasspy/piper/releases",
        _PIPER_MODELS_PATH,
    )
    _piper_cmd_cache = ""   # cache the failure so we don't retry every call
    return None

# ── ElevenLabs client (lazy) ──────────────────────────────────────────────────
_elevenlabs_client = None


def _get_elevenlabs():
    global _elevenlabs_client
    if _elevenlabs_client is None and _ELEVENLABS_API_KEY:
        try:
            from elevenlabs.client import ElevenLabs
            _elevenlabs_client = ElevenLabs(api_key=_ELEVENLABS_API_KEY)
        except Exception as err:
            log.error("ElevenLabs init failed: %s", err)
    return _elevenlabs_client


# ── Public API ────────────────────────────────────────────────────────────────

async def synthesize(text: str, language_code: str = "en") -> str:
    """
    Synthesise *text* in the given language and return base64-encoded audio.
    Returns an empty string on failure — never raises.
    """
    if not text:
        return ""

    route = get_tts_route(language_code)

    try:
        if route.engine == "elevenlabs":
            audio_b64 = _synthesize_elevenlabs(text, route.voice)
            if audio_b64:
                return audio_b64
            # No piper voice exists for ko/ja/zh — English is the only
            # sensible piper fallback here.
            log.warning("ElevenLabs failed, falling back to piper English.")
            return _synthesize_piper(text, "en_US-lessac-medium")

        # route.engine == "piper" — use this language's own voice model.
        audio_b64 = _synthesize_piper(text, route.voice)
        if audio_b64 or route.voice == "en_US-lessac-medium":
            return audio_b64

        # That language's specific model is missing/failed — fall back to
        # English piper rather than silently returning empty audio.
        log.warning(
            "Piper voice '%s' unavailable, falling back to piper English.",
            route.voice,
        )
        return _synthesize_piper(text, "en_US-lessac-medium")

    except Exception as err:
        log.error("TTS synthesis error: %s", err)
        return ""


# ── piper ─────────────────────────────────────────────────────────────────────

# Per-voice sample rate, read once from each voice's .onnx.json and cached —
# every "medium"-tier voice used today happens to be 22050Hz, but that's a
# property of the specific voice files present, not a Piper-wide guarantee
# ("x_low"/"high" tier voices use other rates). Keyed by voice model name.
_voice_sample_rate_cache: dict[str, int] = {}


def _get_sample_rate(voice_model: str) -> int:
    """
    Read the real sample rate for *voice_model* from its .onnx.json config
    (the "audio" -> "sample_rate" key — confirmed present in every voice
    config shipped in piper_models/ today; channels and sample width are
    NOT in this file, see _synthesize_piper()'s call to _pcm_to_wav()).

    Falls back to _DEFAULT_SAMPLE_RATE (with a logged warning) if the config
    is missing, unreadable, or malformed — never raises.
    """
    if voice_model in _voice_sample_rate_cache:
        return _voice_sample_rate_cache[voice_model]

    config_path = _PIPER_MODELS_PATH / f"{voice_model}.onnx.json"
    sample_rate = _DEFAULT_SAMPLE_RATE

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        sample_rate = int(config["audio"]["sample_rate"])
    except FileNotFoundError:
        log.warning(
            "Voice config not found: %s — using default sample rate %dHz.",
            config_path, _DEFAULT_SAMPLE_RATE,
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as err:
        log.warning(
            "Could not read sample rate from %s (%s) — using default %dHz.",
            config_path, err, _DEFAULT_SAMPLE_RATE,
        )

    _voice_sample_rate_cache[voice_model] = sample_rate
    return sample_rate


def _synthesize_piper(text: str, voice_model: str) -> str:
    """
    Run piper-tts as a subprocess and capture the WAV output in memory.
    Returns base64-encoded WAV string, or empty string on failure.
    """
    model_path = _PIPER_MODELS_PATH / f"{voice_model}.onnx"
    config_path = _PIPER_MODELS_PATH / f"{voice_model}.onnx.json"

    if not model_path.exists():
        log.warning(
            "Piper model not found: %s. Returning empty audio.", model_path
        )
        return ""

    piper_cmd = _resolve_piper_cmd()
    if not piper_cmd:
        return ""

    try:
        result = subprocess.run(
            [
                piper_cmd,
                "--model", str(model_path),
                "--config", str(config_path),
                "--output-raw",
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            timeout=30,
        )

        if result.returncode != 0:
            log.error("Piper exited with code %d: %s", result.returncode, result.stderr)
            return ""

        # piper --output-raw always produces mono 16-bit PCM regardless of
        # voice (this is a fixed property of --output-raw itself, not a
        # per-voice setting — confirmed absent from every .onnx.json's
        # "audio" key, which only ever has sample_rate + quality). Sample
        # rate DOES vary per voice/quality-tier, so that one is read from
        # the voice's own config rather than assumed.
        sample_rate = _get_sample_rate(voice_model)
        wav_bytes = _pcm_to_wav(result.stdout, sample_rate=sample_rate, channels=1, sample_width=2)
        return base64.b64encode(wav_bytes).decode("utf-8")

    except FileNotFoundError:
        log.error("piper executable disappeared during run.")
        return ""
    except subprocess.TimeoutExpired:
        log.error("piper timed out.")
        return ""
    except Exception as err:
        log.error("Piper TTS error: %s", err)
        return ""


def _pcm_to_wav(
    pcm_data: bytes,
    sample_rate: int = 22050,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw PCM bytes in a minimal WAV header."""
    import struct

    data_size = len(pcm_data)
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,           # chunk size
        1,            # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        sample_width * 8,
        b"data",
        data_size,
    )
    return header + pcm_data


# ── ElevenLabs ────────────────────────────────────────────────────────────────

def _synthesize_elevenlabs(text: str, voice_env_var: str) -> str:
    """
    Call ElevenLabs TTS API and return base64-encoded MP3.
    Returns empty string on any failure.
    """
    client = _get_elevenlabs()
    if client is None:
        log.warning("ElevenLabs not configured — skipping.")
        return ""

    voice_id = resolve_elevenlabs_voice_id(
        __import__(
            "multilingual.tts_router", fromlist=["TTSRoute"]
        ).TTSRoute(engine="elevenlabs", voice=voice_env_var)
    )
    if not voice_id:
        log.warning("ElevenLabs voice_id not set for env var: %s", voice_env_var)
        return ""

    try:
        audio_iter = client.generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2",
        )
        audio_bytes = b"".join(audio_iter)
        return base64.b64encode(audio_bytes).decode("utf-8")

    except Exception as err:
        log.error("ElevenLabs API error: %s", err)
        return ""
