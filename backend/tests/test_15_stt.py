"""
test_15_stt.py — Tests for voice/stt.py transcription functions.

Mocks the faster-whisper model to avoid loading a real model.
"""

import base64
import struct
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import pytest

from voice.stt import transcribe_bytes, transcribe_base64, TranscribeResult


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_wav_bytes() -> bytes:
    """Build a minimal valid WAV byte sequence for a silent 0.1s clip."""
    sample_rate = 16000
    channels = 1
    sample_width = 2
    num_samples = 1600  # 0.1 seconds
    pcm = b"\x00\x00" * num_samples
    data_size = len(pcm)
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        sample_width * 8,
        b"data",
        data_size,
    )
    return header + pcm


def _build_mock_model(transcript: str = "hello world", lang: str = "en"):
    """Build a mock WhisperModel that returns a fixed transcript."""

    @dataclass
    class MockSegment:
        text: str

    @dataclass
    class MockInfo:
        language: str

    mock_model = MagicMock()
    mock_model.transcribe.return_value = (
        [MockSegment(text=transcript)],
        MockInfo(language=lang),
    )
    return mock_model


# ── transcribe_bytes tests ────────────────────────────────────────────────────

def test_transcribe_bytes_returns_transcribe_result():
    """transcribe_bytes must return a TranscribeResult dataclass."""
    wav = _make_wav_bytes()
    mock_model = _build_mock_model("this is a test", "en")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_bytes(wav)

    assert isinstance(result, TranscribeResult)


def test_transcribe_returns_string():
    """TranscribeResult.transcript must be a string."""
    wav = _make_wav_bytes()
    mock_model = _build_mock_model("hello sir", "en")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_bytes(wav)

    assert isinstance(result.transcript, str)
    assert result.transcript == "hello sir"


def test_transcribe_with_silent_audio_returns_empty_or_handles_gracefully():
    """
    Transcribing a silent WAV (0 PCM bytes) must return a TranscribeResult
    without crashing, with transcript being empty or near-empty.
    """
    result = transcribe_bytes(b"")

    assert isinstance(result, TranscribeResult)
    assert isinstance(result.transcript, str)
    # Empty bytes shortcut returns empty transcript
    assert result.transcript == ""


def test_transcribe_invalid_audio_handled():
    """
    Corrupt/invalid audio bytes must not raise an exception —
    the function must return a TranscribeResult with empty transcript.
    """
    mock_model = MagicMock()
    mock_model.transcribe.side_effect = RuntimeError("invalid audio format")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_bytes(b"not real audio data at all")

    assert isinstance(result, TranscribeResult)
    assert result.transcript == ""


def test_transcribe_language_detection():
    """The language_code in TranscribeResult must reflect the detected language."""
    wav = _make_wav_bytes()
    mock_model = _build_mock_model("こんにちは", "ja")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_bytes(wav)

    assert result.language_code == "ja"


# ── transcribe_base64 tests ────────────────────────────────────────────────────

def test_transcribe_base64_decodes_and_transcribes():
    """transcribe_base64 must decode base64 then call transcribe_bytes."""
    wav = _make_wav_bytes()
    b64 = base64.b64encode(wav).decode("utf-8")
    mock_model = _build_mock_model("base64 input test", "en")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_base64(b64)

    assert isinstance(result, TranscribeResult)
    assert result.transcript == "base64 input test"


def test_transcribe_base64_empty_returns_empty():
    """transcribe_base64 with empty string must return empty TranscribeResult."""
    result = transcribe_base64("")

    assert isinstance(result, TranscribeResult)
    assert result.transcript == ""


def test_transcribe_base64_strips_data_url_prefix():
    """A data-URL prefix (data:audio/webm;base64,...) must be stripped before decode."""
    wav = _make_wav_bytes()
    b64 = base64.b64encode(wav).decode("utf-8")
    data_url = f"data:audio/wav;base64,{b64}"
    mock_model = _build_mock_model("data url stripped", "en")

    with patch("voice.stt._get_model", return_value=mock_model):
        result = transcribe_base64(data_url)

    assert isinstance(result, TranscribeResult)
    assert result.transcript == "data url stripped"


def test_transcribe_base64_invalid_base64_returns_empty():
    """Corrupt base64 must not raise — returns empty TranscribeResult."""
    result = transcribe_base64("!!!not_valid_base64!!!")

    assert isinstance(result, TranscribeResult)
    assert result.transcript == ""


def test_transcribe_model_unavailable_returns_empty():
    """If the Whisper model fails to load (returns None), transcript must be ''."""
    with patch("voice.stt._get_model", return_value=None):
        result = transcribe_bytes(b"some bytes")

    assert isinstance(result, TranscribeResult)
    assert result.transcript == ""
