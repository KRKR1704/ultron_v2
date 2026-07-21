"""
vision/ocr.py — Text extraction from images.

Uses EasyOCR as primary (80+ languages, no config needed).
Falls back to pytesseract for edge cases.
Input is always a base64-encoded image string.
"""

import base64
import io
import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# EasyOCR reader is expensive to initialise — load once, lazily
_easyocr_reader = None


def _get_easyocr():
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            _easyocr_reader = easyocr.Reader(
                ["en", "hi", "ko", "ja", "zh", "fr", "de", "es"],
                gpu=False,
                verbose=False,
            )
            log.info("EasyOCR reader initialised.")
        except Exception as err:
            log.error("EasyOCR init failed: %s", err)
    return _easyocr_reader


def _base64_to_numpy(image_b64: str) -> Optional[np.ndarray]:
    """Decode a base64 image string to an OpenCV-compatible numpy array."""
    try:
        # Strip data-URL prefix if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        raw = base64.b64decode(image_b64)
        from PIL import Image
        img = Image.open(io.BytesIO(raw)).convert("RGB")
        return np.array(img)
    except Exception as err:
        log.error("Image decode failed: %s", err)
        return None


def extract_text(image_b64: str) -> str:
    """
    Extract all text from a base64-encoded image.

    Tries EasyOCR first, falls back to pytesseract.
    Returns an empty string if no text is found or if both engines fail.
    """
    if not image_b64:
        return ""

    img_array = _base64_to_numpy(image_b64)
    if img_array is None:
        return ""

    # ── EasyOCR ───────────────────────────────────────────────────────────────
    reader = _get_easyocr()
    if reader is not None:
        try:
            results = reader.readtext(img_array, detail=0, paragraph=True)
            text = "\n".join(results).strip()
            if text:
                return text
        except Exception as err:
            log.warning("EasyOCR failed: %s — falling back to pytesseract.", err)

    # ── pytesseract fallback ──────────────────────────────────────────────────
    try:
        import pytesseract
        from PIL import Image

        pil_image = Image.fromarray(img_array)
        text = pytesseract.image_to_string(pil_image).strip()
        return text
    except ImportError:
        log.warning("pytesseract not installed — no OCR fallback available.")
        return ""
    except Exception as err:
        log.error("pytesseract failed: %s", err)
        return ""
