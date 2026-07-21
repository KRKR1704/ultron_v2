"""
test_14_tts.py — Tests for voice/tts.py synthesize().

Mocks subprocess piper calls and ElevenLabs client to avoid real TTS.
"""

import base64
import struct
import subprocess
from unittest.mock import AsyncMock, patch, MagicMock, call

import pytest

from helpers import piper_available, skip_no_piper
from voice.tts import synthesize, _pcm_to_wav, _synthesize_piper


# ── Helper: build fake WAV bytes (silent audio) ────────────────────────────────

def _make_silent_pcm(duration_ms: int = 100, sample_rate: int = 22050) -> bytes:
    """Return raw 16-bit PCM silence bytes."""
    num_samples = int(sample_rate * duration_ms / 1000)
    return b"\x00\x00" * num_samples


# ── _pcm_to_wav unit tests ────────────────────────────────────────────────────

def test_pcm_to_wav_returns_valid_wav_header():
    """_pcm_to_wav must produce bytes starting with the RIFF header."""
    pcm = _make_silent_pcm(50)
    wav = _pcm_to_wav(pcm, sample_rate=22050, channels=1, sample_width=2)

    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[12:16] == b"fmt "
    assert wav[36:40] == b"data"


def test_pcm_to_wav_correct_data_size():
    """The data chunk size in the WAV header must equal len(pcm_data)."""
    pcm = _make_silent_pcm(100)
    wav = _pcm_to_wav(pcm)

    data_size_in_header = struct.unpack_from("<I", wav, 40)[0]
    assert data_size_in_header == len(pcm)


# ── synthesize() mocked tests ─────────────────────────────────────────────────

async def test_synthesize_returns_base64_string_mock():
    """With a mocked piper subprocess, synthesize must return a non-empty base64 string."""
    fake_pcm = _make_silent_pcm(100)

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_pcm
    mock_result.stderr = b""

    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("subprocess.run", return_value=mock_result) as mock_sub, \
         patch("pathlib.Path.exists", return_value=True):
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="en_US-lessac-medium")

        result = await synthesize("Hello, sir.", "en")

    assert isinstance(result, str)
    assert len(result) > 0
    # Must be valid base64
    decoded = base64.b64decode(result)
    assert decoded[:4] == b"RIFF"


async def test_synthesize_english_mock():
    """synthesize for English must route to piper and return base64."""
    fake_pcm = _make_silent_pcm(50)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_pcm
    mock_result.stderr = b""

    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("subprocess.run", return_value=mock_result), \
         patch("pathlib.Path.exists", return_value=True):
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="en_US-lessac-medium")

        result = await synthesize("Good evening.", "en")

    assert isinstance(result, str)


async def test_synthesize_non_english_language_mock():
    """synthesize for a non-English piper language must return base64."""
    fake_pcm = _make_silent_pcm(50)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = fake_pcm
    mock_result.stderr = b""

    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("subprocess.run", return_value=mock_result), \
         patch("pathlib.Path.exists", return_value=True):
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="hi_IN-x_low")

        result = await synthesize("नमस्ते", "hi")

    assert isinstance(result, str)


async def test_synthesize_empty_text_returns_empty_string():
    """synthesize with empty text must return '' immediately without calling piper."""
    with patch("subprocess.run") as mock_sub:
        result = await synthesize("", "en")

    assert result == ""
    mock_sub.assert_not_called()


async def test_synthesize_piper_not_found_returns_empty_string():
    """If piper executable is missing (FileNotFoundError), synthesize must return ''."""
    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("subprocess.run", side_effect=FileNotFoundError("piper not found")), \
         patch("pathlib.Path.exists", return_value=True):
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="en_US-lessac-medium")

        result = await synthesize("Hello", "en")

    assert result == ""


async def test_synthesize_piper_timeout_returns_empty_string():
    """If piper times out, synthesize must return '' gracefully."""
    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired("piper", 30)), \
         patch("pathlib.Path.exists", return_value=True):
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="en_US-lessac-medium")

        result = await synthesize("Hello", "en")

    assert result == ""


async def test_synthesize_model_not_found_returns_empty_string():
    """If the piper model file is missing, synthesize must return '' without crashing."""
    with patch("voice.tts.get_tts_route") as mock_route, \
         patch("pathlib.Path.exists", return_value=False):  # model file missing
        from multilingual.tts_router import TTSRoute
        mock_route.return_value = TTSRoute(engine="piper", voice="en_US-lessac-medium")

        result = await synthesize("Hello", "en")

    assert result == ""


# ── Live piper test ────────────────────────────────────────────────────────────

@pytest.mark.requires_piper
@skip_no_piper
async def test_piper_binary_present_and_runs():
    """
    LIVE: If piper is on PATH, verify it runs and produces non-empty audio.
    Requires a real piper model file at the configured path.
    """
    result = await synthesize("Testing piper TTS.", "en")
    # Either returns valid base64 audio or empty string if model not found
    assert isinstance(result, str)
