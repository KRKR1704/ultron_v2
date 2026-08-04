"""
voice/wake_word.py — Native "Ultron" wake-word detection via a custom-trained
OpenWakeWord model (backend/wake_word_models/ultron_v2.onnx), plus the
follow-up command capture that runs after a detection.

Replaces the prior hey_jarvis + Whisper-confirmation workaround. That
workaround existed because the first custom-model attempt (2026-07-23)
failed its runtime validation gate due to a train/inference feature-
extraction mismatch (see AUDIT_REPORT.md Fix Pass History entry 7).
ultron_v2.onnx was retrained using the streaming-matched feature pipeline
(wake_word_training/prepare_data_streaming.py) and passed the same runtime
validation gate cleanly on real audio, including phonetically-close
near-homophones ("oltron"/"altron"/"eltron"/"aldron") and phrases never
used in training — see wake_word_training/validate_model_v2.py.

OpenWakeWord runs in a background thread; a positive score directly fires
the activation event (no secondary Whisper confirmation step — the model's
own validated discrimination is now trusted directly).

State machine (all transitions happen inside the single sounddevice audio
callback thread, so no locking is needed for the state itself — the only
cross-thread activity is handing finished, immutable data off to fresh
threads for on_activation/on_command_captured, and the external
resume_passive_listening() call flipping one attribute back):

  PASSIVE     — feeding every chunk to the wake-word model, scoring for
                "ultron".
  CAPTURING   — wake word just fired. Not scoring for "ultron" anymore
                (avoids re-triggering on the follow-up command); instead
                buffering raw audio and RMS-endpointing it: give up early
                if nothing is said within _CAPTURE_NO_SPEECH_TIMEOUT,
                otherwise stop _CAPTURE_SILENCE_HANG_SECONDS after speech
                trails off, capped at _CAPTURE_MAX_SECONDS either way.
  PROCESSING  — capture finished, handed off to on_command_captured() for
                STT -> agent -> TTS (see api/websocket.py's
                process_wake_word_command()). Still not scoring for
                "ultron" — the app shouldn't re-trigger on its own
                follow-up processing/response. Stays here until the
                caller explicitly calls resume_passive_listening(), which
                that pipeline does in a finally block so a stuck/errored
                turn can never permanently disable the detector.

The thread is cleanly started/stopped via threading.Event.
"""

import io
import logging
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Optional

import numpy as np

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_SAMPLE_RATE = 16000
_CHUNK_DURATION_MS = 80          # ms per audio chunk
_CHUNK_SAMPLES = int(_SAMPLE_RATE * _CHUNK_DURATION_MS / 1000)
_OWW_THRESHOLD = 0.5             # confidence threshold
_TRIGGER_COOLDOWN_SECONDS = 2.0  # minimum gap between activations (debounce)

_MODEL_PATH = Path(__file__).parent.parent / "wake_word_models" / "ultron_v2.onnx"
_WAKE_WORD_LABEL = "ultron_v2"

# ── Follow-up command capture configuration ────────────────────────────────────
_CAPTURE_SPEECH_RMS_THRESHOLD = 150.0   # int16 RMS above this = "someone is talking"
                                         # (well above the <20 room-noise floor and
                                         # well below the 700+ real-speech-burst RMS
                                         # measured during positive-sample validation)
_CAPTURE_MAX_SECONDS = 8.0              # hard cap regardless of speech activity
_CAPTURE_NO_SPEECH_TIMEOUT = 3.0        # give up if nothing said within this long
_CAPTURE_SILENCE_HANG_SECONDS = 1.0     # stop this long after speech trails off

# Optional callback signatures
ActivationCallback = Callable[[], None]
CommandCapturedCallback = Callable[[bytes], None]  # receives a complete WAV file


def _encode_wav(samples: np.ndarray, sample_rate: int = _SAMPLE_RATE) -> bytes:
    """Wrap raw int16 PCM samples into a complete, valid WAV file in memory.
    voice/stt.py's transcribe_bytes() writes its input straight to a .wav
    temp file for faster-whisper to decode, so it needs a real WAV
    container, not headerless PCM."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # int16
        w.setframerate(sample_rate)
        w.writeframes(samples.tobytes())
    return buf.getvalue()


def _should_end_capture(
    elapsed: float,
    speech_started: bool,
    time_since_last_speech: float,
) -> bool:
    """
    Pure decision function for whether the follow-up command capture
    window should close now — separated out from the audio callback so
    it's directly unit-testable without a live audio stream.
    """
    if elapsed >= _CAPTURE_MAX_SECONDS:
        return True
    if not speech_started and elapsed >= _CAPTURE_NO_SPEECH_TIMEOUT:
        return True
    if speech_started and time_since_last_speech >= _CAPTURE_SILENCE_HANG_SECONDS:
        return True
    return False


class WakeWordDetector:
    """
    Manages the OpenWakeWord background listener and the follow-up
    command capture that runs after a detection.

    Usage:
        detector = WakeWordDetector(
            on_activation=my_callback,
            on_command_captured=my_command_callback,
        )
        detector.start()
        ...
        detector.stop()
    """

    def __init__(
        self,
        on_activation: Optional[ActivationCallback] = None,
        on_command_captured: Optional[CommandCapturedCallback] = None,
    ) -> None:
        self._on_activation = on_activation
        self._on_command_captured = on_command_captured
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False

        # Capture state machine. "mode" is read/written by the audio
        # callback thread on every chunk, and written once from an
        # external thread by resume_passive_listening() — a plain string
        # attribute assignment is atomic under the GIL, so no lock needed.
        self._mode = "passive"  # "passive" | "capturing" | "processing"
        self._oww_model = None  # set once loaded, so resume can call .reset()

    # ── Public control ────────────────────────────────────────────────────────

    def start(
        self,
        on_activation: Optional[ActivationCallback] = None,
        on_command_captured: Optional[CommandCapturedCallback] = None,
    ) -> None:
        if self._thread and self._thread.is_alive():
            return
        if on_activation is not None:
            self._on_activation = on_activation
        if on_command_captured is not None:
            self._on_command_captured = on_command_captured
        self._stop_event.clear()
        self._active = True
        self._mode = "passive"
        self._thread = threading.Thread(
            target=self._run,
            name="wake-word-listener",
            daemon=True,
        )
        self._thread.start()
        log.info("Wake word detector started.")

    def stop(self) -> None:
        self._stop_event.set()
        self._active = False
        if self._thread:
            self._thread.join(timeout=5.0)
        log.info("Wake word detector stopped.")

    def resume_passive_listening(self) -> None:
        """
        Called by the follow-up-command pipeline (api/websocket.py's
        process_wake_word_command()) once STT/agent/TTS processing has
        finished (success OR failure — always in a finally block there),
        so the detector never gets permanently stuck off "ultron"
        detection after a single turn.
        """
        if self._oww_model is not None:
            try:
                self._oww_model.reset()
            except Exception:
                pass
        self._mode = "passive"

    @property
    def is_active(self) -> bool:
        return self._active and (self._thread is not None and self._thread.is_alive())

    # ── Background thread ─────────────────────────────────────────────────────

    def _run(self) -> None:
        """Main detection loop — runs in a daemon thread."""
        try:
            import sounddevice as sd
            from openwakeword.model import Model as OWWModel

            if not _MODEL_PATH.exists():
                log.warning(
                    "Custom wake word model not found at %s — wake word disabled.",
                    _MODEL_PATH,
                )
                self._active = False
                return

            oww = OWWModel(
                wakeword_models=[str(_MODEL_PATH)],
                class_mapping_dicts=[{"0": _WAKE_WORD_LABEL}],
                inference_framework="onnx",
            )
            self._oww_model = oww
            log.info("Custom 'ultron' wake word model loaded from %s.", _MODEL_PATH)

            last_trigger_time = 0.0

            # Capture-window state — only touched from this callback thread.
            capture_chunks: list[np.ndarray] = []
            capture_start = 0.0
            speech_started = False
            last_speech_time = 0.0

            def audio_callback(indata: np.ndarray, frames, time_info, status):
                nonlocal last_trigger_time, capture_chunks, capture_start
                nonlocal speech_started, last_speech_time

                if self._stop_event.is_set():
                    raise sd.CallbackStop()

                chunk = indata[:, 0] if indata.ndim > 1 else indata.flatten()
                chunk_int16 = (chunk * 32767).astype(np.int16)
                now = time.monotonic()

                if self._mode == "passive":
                    prediction = oww.predict(chunk_int16)
                    score = prediction.get(_WAKE_WORD_LABEL, 0.0)

                    if score >= _OWW_THRESHOLD and (now - last_trigger_time) > _TRIGGER_COOLDOWN_SECONDS:
                        last_trigger_time = now
                        log.info("Wake word 'ultron' detected (score=%.3f). Firing activation.", score)
                        if self._on_activation:
                            threading.Thread(target=self._on_activation, daemon=True).start()

                        # Switch to capturing the follow-up command instead
                        # of continuing to score for "ultron" — avoids
                        # re-triggering on the command itself.
                        self._mode = "capturing"
                        capture_chunks = []
                        capture_start = now
                        speech_started = False
                        last_speech_time = now

                elif self._mode == "capturing":
                    capture_chunks.append(chunk_int16.copy())
                    rms = float(np.sqrt(np.mean(chunk_int16.astype(np.float64) ** 2)))

                    if rms > _CAPTURE_SPEECH_RMS_THRESHOLD:
                        speech_started = True
                        last_speech_time = now

                    elapsed = now - capture_start
                    if _should_end_capture(elapsed, speech_started, now - last_speech_time):
                        captured = (
                            np.concatenate(capture_chunks)
                            if capture_chunks
                            else np.array([], dtype=np.int16)
                        )
                        capture_chunks = []
                        # Stop scoring AND stop capturing while the command
                        # is processed — resumed externally via
                        # resume_passive_listening() once the turn is done.
                        self._mode = "processing"

                        log.info(
                            "Follow-up command captured (%.2fs, speech_detected=%s).",
                            elapsed, speech_started,
                        )
                        if self._on_command_captured:
                            wav_bytes = _encode_wav(captured)
                            threading.Thread(
                                target=self._on_command_captured,
                                args=(wav_bytes,),
                                daemon=True,
                            ).start()
                        else:
                            # No handler registered — don't get stuck.
                            self._mode = "passive"

                # "processing" mode: don't score, don't capture. Waiting
                # for an external resume_passive_listening() call.

            with sd.InputStream(
                samplerate=_SAMPLE_RATE,
                blocksize=_CHUNK_SAMPLES,
                dtype="float32",
                channels=1,
                callback=audio_callback,
            ):
                while not self._stop_event.is_set():
                    self._stop_event.wait(timeout=0.5)

        except ImportError as err:
            log.warning(
                "Wake word detection unavailable — missing dependency: %s. "
                "Install sounddevice and openwakeword to enable it.",
                err,
            )
            self._active = False
        except Exception as err:
            log.error("Wake word thread crashed: %s", err)
            self._active = False


# ── Module-level singleton ────────────────────────────────────────────────────
wake_word_detector = WakeWordDetector()
