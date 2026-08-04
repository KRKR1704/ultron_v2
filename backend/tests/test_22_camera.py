"""
test_22_camera.py — Tests for Bug 2: dead unknown-face callback wiring.

main.py defines a real on_unknown_face callback and passes it into
camera_capture.start(), but vision/camera.py's _analyse_frame() never
actually invoked it — the callback was accepted and then dropped on the
floor. This is independent of the separately-documented face_recognition/
dlib installation blocker (see AUDIT_REPORT.md Known Deferred Items).

Since face_recognition/dlib is not installed in this environment, these
tests mock the face_recognition module entirely (passed directly into
_analyse_frame(), bypassing the real import) to prove the wiring itself is
correct — that IF face_recognition were installed and returned an encoding
that doesn't match any known face, the callback WOULD fire with the
expected (zero-argument) signature that main.py's _on_unknown_face expects.
"""

from unittest.mock import MagicMock

import numpy as np

from vision.camera import CameraCapture


def _fake_frame() -> np.ndarray:
    return np.zeros((10, 10, 3), dtype=np.uint8)


def _fake_face_det_with_detection():
    """A mediapipe-shaped face detector mock that reports one detected face."""
    face_det = MagicMock()
    results = MagicMock()
    results.detections = [MagicMock()]
    face_det.process.return_value = results
    return face_det


def _fake_face_det_no_detection():
    face_det = MagicMock()
    results = MagicMock()
    results.detections = None
    face_det.process.return_value = results
    return face_det


def test_unknown_face_callback_fires_when_no_known_match():
    """
    A detected face whose encoding matches nothing in the known-faces list
    must trigger on_unknown_face(), with no arguments — matching main.py's
    real _on_unknown_face() signature exactly.
    """
    camera = CameraCapture()
    callback = MagicMock()
    camera._on_unknown_face = callback
    camera._known_face_encodings = []

    fake_face_recognition = MagicMock()
    fake_face_recognition.face_encodings.return_value = [np.zeros(128)]
    fake_face_recognition.compare_faces.return_value = [False]  # no match -> unknown

    camera._analyse_frame(_fake_frame(), _fake_face_det_with_detection(), fake_face_recognition)

    callback.assert_called_once_with()


def test_known_face_does_not_fire_callback():
    """A face that DOES match a known encoding must NOT trigger the callback."""
    camera = CameraCapture()
    callback = MagicMock()
    camera._on_unknown_face = callback
    camera._known_face_encodings = [np.ones(128)]

    fake_face_recognition = MagicMock()
    fake_face_recognition.face_encodings.return_value = [np.ones(128)]
    fake_face_recognition.compare_faces.return_value = [True]  # match -> known

    camera._analyse_frame(_fake_frame(), _fake_face_det_with_detection(), fake_face_recognition)

    callback.assert_not_called()


def test_no_face_detected_does_not_fire_callback():
    """No face in frame at all must not trigger the callback or crash."""
    camera = CameraCapture()
    callback = MagicMock()
    camera._on_unknown_face = callback

    fake_face_recognition = MagicMock()

    camera._analyse_frame(_fake_frame(), _fake_face_det_no_detection(), fake_face_recognition)

    callback.assert_not_called()
    fake_face_recognition.face_encodings.assert_not_called()


def test_face_recognition_unavailable_does_not_crash():
    """
    When face_recognition is None (the real state today, since dlib isn't
    installed), a detected face must not crash and must not fire the
    callback — mediapipe detection still runs, but recognition is skipped.
    """
    camera = CameraCapture()
    callback = MagicMock()
    camera._on_unknown_face = callback

    camera._analyse_frame(_fake_frame(), _fake_face_det_with_detection(), None)

    callback.assert_not_called()


def test_no_callback_registered_does_not_crash():
    """If start() was never called with on_unknown_face, analysis must still not crash."""
    camera = CameraCapture()
    assert camera._on_unknown_face is None

    fake_face_recognition = MagicMock()
    fake_face_recognition.face_encodings.return_value = [np.zeros(128)]
    fake_face_recognition.compare_faces.return_value = [False]

    # Must not raise even though there's no callback to call.
    camera._analyse_frame(_fake_frame(), _fake_face_det_with_detection(), fake_face_recognition)
