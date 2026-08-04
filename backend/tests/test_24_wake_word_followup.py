"""
test_24_wake_word_followup.py — Tests for the wake-word "listen -> understand
-> respond" loop added after wake-word activation.

Covers:
  - voice/wake_word.py's pure capture-endpointing decision function
    (_should_end_capture) and WAV encoding (_encode_wav), directly —
    no live audio stream needed.
  - WakeWordDetector.resume_passive_listening().
  - api/websocket.py's process_wake_word_command(), which reuses
    api.routes.voice.run_stt_agent_tts (the same pipeline POST /voice
    uses) — mocked the same way test_18_websocket.py mocks the
    per-connection audio path, since the underlying pipeline is identical.
"""

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from voice.wake_word import WakeWordDetector, _encode_wav, _should_end_capture


# ── Helpers ────────────────────────────────────────────────────────────────────

@dataclass
class _FakeSTTResult:
    transcript: str
    language: str = "English"
    language_code: str = "en"


def _mock_stt(transcript: str = "what time is it"):
    return _FakeSTTResult(transcript=transcript, language="English", language_code="en")


# ── _should_end_capture() — pure decision logic ────────────────────────────────

def test_capture_ends_at_max_duration_regardless_of_speech():
    assert _should_end_capture(elapsed=8.0, speech_started=False, time_since_last_speech=0.0) is True
    assert _should_end_capture(elapsed=8.0, speech_started=True, time_since_last_speech=0.0) is True


def test_capture_ends_early_when_nobody_speaks():
    """'Ultron' then silence — give up well before the max cap."""
    assert _should_end_capture(elapsed=3.0, speech_started=False, time_since_last_speech=0.0) is True


def test_capture_does_not_end_early_while_still_within_no_speech_grace_period():
    assert _should_end_capture(elapsed=1.0, speech_started=False, time_since_last_speech=0.0) is False


def test_capture_ends_after_silence_hang_following_speech():
    """User spoke, then paused for >= the silence-hang window — command is done."""
    assert _should_end_capture(elapsed=4.0, speech_started=True, time_since_last_speech=1.0) is True


def test_capture_continues_while_user_is_actively_speaking():
    assert _should_end_capture(elapsed=4.0, speech_started=True, time_since_last_speech=0.1) is False


# ── _encode_wav() ────────────────────────────────────────────────────────────

def test_encode_wav_produces_valid_readable_wav():
    import io
    import wave

    samples = (np.sin(np.linspace(0, 10, 1600)) * 10000).astype(np.int16)
    wav_bytes = _encode_wav(samples, sample_rate=16000)

    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getframerate() == 16000
        assert w.getnframes() == len(samples)


def test_encode_wav_handles_empty_samples():
    wav_bytes = _encode_wav(np.array([], dtype=np.int16))
    assert len(wav_bytes) > 0  # still a valid (empty-data) WAV header


# ── WakeWordDetector.resume_passive_listening() ────────────────────────────────

def test_resume_passive_listening_resets_mode():
    detector = WakeWordDetector()
    detector._mode = "processing"
    detector.resume_passive_listening()
    assert detector._mode == "passive"


def test_resume_passive_listening_safe_with_no_model_loaded():
    """Must not crash if called before/without the oww model ever loading."""
    detector = WakeWordDetector()
    detector._mode = "capturing"
    detector.resume_passive_listening()  # should not raise
    assert detector._mode == "passive"


# ── process_wake_word_command() ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_process_wake_word_command_runs_full_pipeline_and_broadcasts():
    """Happy path: transcript -> agent -> TTS -> broadcast frames, in order."""
    from api.websocket import process_wake_word_command

    broadcasts = []

    async def _record_broadcast(msg):
        broadcasts.append(msg)

    with patch("api.websocket.transcribe_bytes", return_value=_mock_stt("what time is it")), \
         patch("api.websocket.manager.broadcast", side_effect=_record_broadcast), \
         patch("api.routes.voice.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("voice.wake_word.wake_word_detector.resume_passive_listening") as mock_resume:

        mock_agent.return_value = "It is 3 PM, sir."
        mock_tts.return_value = "ZmFrZWF1ZGlv"  # base64 "fakeaudio"

        await process_wake_word_command(b"fake-wav-bytes")

    mock_agent.assert_called_once()
    assert mock_agent.call_args.kwargs["text"] == "what time is it"
    mock_tts.assert_called_once()
    mock_resume.assert_called_once()

    types = [b["type"] for b in broadcasts]
    assert types == ["transcript", "token", "audio_generating", "audio", "done"]
    assert broadcasts[0]["text"] == "what time is it"
    assert broadcasts[1]["text"] == "It is 3 PM, sir."
    assert broadcasts[3]["audio_base64"] == "ZmFrZWF1ZGlv"


@pytest.mark.asyncio
async def test_process_wake_word_command_silence_never_reaches_agent():
    """
    'Ultron' followed by silence/noise (empty transcript) must NOT call the
    agent at all — reuses run_stt_agent_tts's existing graceful fallback,
    same as POST /voice, so silence can never be hallucinated into an answer.
    """
    from api.websocket import process_wake_word_command

    broadcasts = []

    async def _record_broadcast(msg):
        broadcasts.append(msg)

    with patch("api.websocket.transcribe_bytes", return_value=_mock_stt("")), \
         patch("api.websocket.manager.broadcast", side_effect=_record_broadcast), \
         patch("api.routes.voice.run_agent", new_callable=AsyncMock) as mock_agent, \
         patch("api.routes.voice.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("voice.wake_word.wake_word_detector.resume_passive_listening") as mock_resume:

        mock_tts.return_value = "ZmFrZWF1ZGlv"

        await process_wake_word_command(b"silence-wav-bytes")

    mock_agent.assert_not_called()
    mock_tts.assert_called_once()
    mock_resume.assert_called_once()

    token_frame = next(b for b in broadcasts if b["type"] == "token")
    assert "didn't catch that" in token_frame["text"].lower()


@pytest.mark.asyncio
async def test_process_wake_word_command_always_resumes_detector_on_error():
    """
    A hard failure (e.g. transcription itself raising) must still resume
    passive listening — never leave the detector permanently stuck off
    "ultron" detection after one bad turn.
    """
    from api.websocket import process_wake_word_command

    async def _record_broadcast(msg):
        pass

    with patch("api.websocket.transcribe_bytes", side_effect=RuntimeError("boom")), \
         patch("api.websocket.manager.broadcast", side_effect=_record_broadcast), \
         patch("voice.wake_word.wake_word_detector.resume_passive_listening") as mock_resume:

        await process_wake_word_command(b"bad-bytes")  # must not raise

    mock_resume.assert_called_once()
