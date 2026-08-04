"""
vision/camera.py — Webcam capture (passive monitoring + on-demand).

Passive mode runs in a background thread at ~1 fps using OpenCV.
Frames are NEVER saved to disk — only held in memory.
On-demand capture returns a single JPEG frame as a base64 string.
"""

import base64
import logging
import threading
import time
from typing import Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

_PASSIVE_FPS   = 15.0   # background capture rate — enough for smooth streaming
_JPEG_QUALITY  = 75    # lower quality = smaller frames = faster stream


class CameraCapture:
    """Manages passive webcam monitoring and on-demand frame capture."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._on_unknown_face = None
        # Known-face encodings to compare detected faces against. No
        # enrollment feature exists yet (a separate feature, not this bug),
        # so this stays empty — meaning every detected face is correctly
        # treated as unknown, since there is nothing to recognize it as.
        self._known_face_encodings: list = []

    # ── Public control ────────────────────────────────────────────────────────

    def start(self, on_unknown_face=None) -> None:
        """Start the passive monitoring background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._on_unknown_face = on_unknown_face
        self._stop_event.clear()
        self._active = True
        self._thread = threading.Thread(
            target=self._run_passive,
            name="camera-monitor",
            daemon=True,
        )
        self._thread.start()
        log.info("Camera passive monitor started.")

    def stop(self) -> None:
        self._stop_event.set()
        self._active = False
        if self._thread:
            self._thread.join(timeout=5.0)
        log.info("Camera passive monitor stopped.")

    @property
    def is_active(self) -> bool:
        return self._active and (self._thread is not None and self._thread.is_alive())

    # ── On-demand capture ─────────────────────────────────────────────────────

    def capture_frame(self) -> str:
        """
        Capture a single frame from the webcam.
        Returns a base64-encoded JPEG string, or empty string on failure.
        Frame is NEVER written to disk.
        """
        # If passive thread is running, return the latest cached frame
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._encode_frame(self._latest_frame)

        # Otherwise open camera, grab one frame, release immediately
        return self._grab_single_frame()

    # ── Background thread ─────────────────────────────────────────────────────

    def _run_passive(self) -> None:
        try:
            import face_recognition
            import mediapipe as mp

            mp_face = mp.solutions.face_detection
            face_det = mp_face.FaceDetection(min_detection_confidence=0.5)

        except ImportError as err:
            log.warning(
                "Face/mediapipe detection unavailable: %s. "
                "Running camera without face analysis.",
                err,
            )
            face_det = None
            face_recognition = None

        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            log.warning("Cannot open webcam — passive monitoring disabled.")
            return

        interval = 1.0 / _PASSIVE_FPS

        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(interval)
                continue

            with self._frame_lock:
                self._latest_frame = frame.copy()

            if face_det is not None:
                self._analyse_frame(frame, face_det, face_recognition)

            self._stop_event.wait(timeout=interval)

        cap.release()
        face_det and face_det.close()

    def _analyse_frame(self, frame: np.ndarray, face_det, face_recognition=None) -> None:
        """
        Run mediapipe face detection on a frame, then — when face_recognition
        is available — compute an encoding for each detected face and fire
        on_unknown_face for any face that doesn't match a known encoding.

        Callback wiring fixed 2026-08-03 — still requires face_recognition/
        dlib installed to actually trigger with real camera input; see
        AUDIT_REPORT.md Known Deferred Items for that separate blocker.
        """
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_det.process(rgb)

            if results.detections:
                log.debug("Face detected in camera frame.")

                if face_recognition is not None:
                    encodings = face_recognition.face_encodings(rgb)
                    for encoding in encodings:
                        matches = face_recognition.compare_faces(
                            self._known_face_encodings, encoding
                        )
                        if not any(matches) and self._on_unknown_face:
                            self._on_unknown_face()

        except Exception as err:
            log.debug("Frame analysis error: %s", err)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _grab_single_frame(self) -> str:
        """Open the camera, capture one frame, close immediately."""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            log.error("Cannot open webcam for on-demand capture.")
            return ""
        try:
            ret, frame = cap.read()
            if not ret:
                return ""
            return self._encode_frame(frame)
        finally:
            cap.release()

    @staticmethod
    def _encode_frame(frame: np.ndarray) -> str:
        """Encode an OpenCV frame to base64 JPEG — entirely in memory."""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, _JPEG_QUALITY]
        _, buffer = cv2.imencode(".jpg", frame, encode_params)
        return base64.b64encode(buffer.tobytes()).decode("utf-8")


# ── Module-level singleton ────────────────────────────────────────────────────
camera_capture = CameraCapture()
