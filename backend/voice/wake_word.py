"""
voice/wake_word.py — Hybrid OpenWakeWord + Whisper wake-word detection.

OpenWakeWord runs in a background thread listening for "hey ultron" /
"ultron" / "yo ultron".  On a positive hit, faster-whisper confirms the
spoken phrase before firing the activation event.

The thread is cleanly started/stopped via threading.Event.
"""

import base64
import logging
import queue
import threading
from typing import Callable, Optional

import numpy as np

log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
_SAMPLE_RATE = 16000
_CHUNK_DURATION_MS = 80          # ms per audio chunk
_CHUNK_SAMPLES = int(_SAMPLE_RATE * _CHUNK_DURATION_MS / 1000)
_OWW_THRESHOLD = 0.5             # confidence threshold
# Built-in OpenWakeWord models — use "hey_jarvis" as the closest available
# wake word, or "alexa" / "hey_mycroft". Custom "ultron" model requires training.
_WAKE_WORDS = ["hey_jarvis"]

# Optional callback signature: () -> None
ActivationCallback = Callable[[], None]


class WakeWordDetector:
    """
    Manages the OpenWakeWord background listener.

    Usage:
        detector = WakeWordDetector(on_activation=my_callback)
        detector.start()
        ...
        detector.stop()
    """

    def __init__(self, on_activation: Optional[ActivationCallback] = None) -> None:
        self._on_activation = on_activation
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False

    # ── Public control ────────────────────────────────────────────────────────

    def start(self, on_activation: Optional[ActivationCallback] = None) -> None:
        if self._thread and self._thread.is_alive():
            return
        if on_activation is not None:
            self._on_activation = on_activation
        self._stop_event.clear()
        self._active = True
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

    @property
    def is_active(self) -> bool:
        return self._active and (self._thread is not None and self._thread.is_alive())

    # ── Background thread ─────────────────────────────────────────────────────

    def _run(self) -> None:
        """Main detection loop — runs in a daemon thread."""
        try:
            import sounddevice as sd
            from openwakeword.model import Model as OWWModel
            import openwakeword.utils as oww_utils

            # Download wake word models if not already present on disk.
            # This is a no-op when the .onnx files already exist.
            try:
                log.info("Ensuring OpenWakeWord models are downloaded...")
                oww_utils.download_models(_WAKE_WORDS)
                log.info("OpenWakeWord models ready.")
            except Exception as dl_err:
                log.warning(
                    "Could not download OpenWakeWord models (%s) — wake word disabled.",
                    dl_err,
                )
                self._active = False
                return

            oww = OWWModel(wakeword_models=_WAKE_WORDS, inference_framework="onnx")
            log.info("OpenWakeWord model loaded.")

            # Buffer to accumulate audio for Whisper confirmation
            confirm_buffer: list[np.ndarray] = []
            confirmed = False
            confirm_frames_needed = int(_SAMPLE_RATE * 2 / _CHUNK_SAMPLES)  # ~2s

            def audio_callback(indata: np.ndarray, frames, time, status):
                nonlocal confirm_buffer, confirmed
                if self._stop_event.is_set():
                    raise sd.CallbackStop()

                chunk = indata[:, 0] if indata.ndim > 1 else indata.flatten()
                chunk_int16 = (chunk * 32767).astype(np.int16)

                # Feed to OWW
                prediction = oww.predict(chunk_int16)

                triggered = any(
                    score >= _OWW_THRESHOLD
                    for score in prediction.values()
                )

                if triggered and not confirmed:
                    log.info("Wake word candidate detected — confirming with Whisper.")
                    confirm_buffer = [chunk_int16]
                    confirmed = True
                elif confirmed:
                    confirm_buffer.append(chunk_int16)
                    if len(confirm_buffer) >= confirm_frames_needed:
                        self._confirm_with_whisper(confirm_buffer)
                        confirm_buffer = []
                        confirmed = False

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

    def _confirm_with_whisper(self, audio_chunks: list[np.ndarray]) -> None:
        """
        Concatenate chunks and run faster-whisper to confirm the wake word.
        Fires the activation callback if 'ultron' is found in the transcript.
        """
        try:
            from voice.stt import transcribe_bytes
            import scipy.io.wavfile as wav_module
            import io

            audio = np.concatenate(audio_chunks).astype(np.int16)
            buf = io.BytesIO()
            wav_module.write(buf, _SAMPLE_RATE, audio)
            audio_bytes = buf.getvalue()

            result = transcribe_bytes(audio_bytes)
            log.info("Wake confirmation transcript: '%s'", result.transcript)

            if "ultron" in result.transcript.lower():
                log.info("Wake word confirmed! Firing activation.")
                if self._on_activation:
                    threading.Thread(
                        target=self._on_activation,
                        daemon=True,
                    ).start()

        except Exception as err:
            log.error("Whisper confirmation failed: %s", err)


# ── Module-level singleton ────────────────────────────────────────────────────
wake_word_detector = WakeWordDetector()
