"""
vision/ocr.py — Text extraction from images.

Uses EasyOCR as primary, falls back to pytesseract for edge cases.
Input is always a base64-encoded image string.

EasyOCR does NOT allow arbitrary language lists to be combined in one
Reader — non-Latin scripts (Hindi/Devanagari, Korean, Japanese, Chinese)
are each only compatible with English, not with each other or with the
other Latin-alphabet languages. A single Reader across
en+hi+ko+ja+zh+fr+de+es (the previous configuration) throws on
construction for exactly this reason. Instead we keep one Reader per
compatible language *group* and lazily build only the group that is
actually requested via `language_code`, selecting the group with
`_group_for_language()`.
"""

import base64
import io
import logging
from typing import Optional

import numpy as np

log = logging.getLogger(__name__)

# ── EasyOCR-compatible language groups ────────────────────────────────────────
# Each group is a set of language codes that EasyOCR allows in a single Reader.
# "ch_sim" is EasyOCR's code for simplified Chinese (NOT "zh", which is invalid
# and throws "is not supported" on Reader construction).
_LATIN_GROUP: list[str] = ["en", "fr", "de", "es"]

_LANGUAGE_TO_GROUP: dict[str, list[str]] = {
    "en": _LATIN_GROUP,
    "fr": _LATIN_GROUP,
    "de": _LATIN_GROUP,
    "es": _LATIN_GROUP,
    "hi": ["en", "hi"],
    "ko": ["en", "ko"],
    "ja": ["en", "ja"],
    "zh": ["en", "ch_sim"],
}

# Readers are expensive to build — cache one per group, lazily, keyed by the
# tuple of language codes so the same group is never constructed twice.
_easyocr_readers: dict[tuple, Optional["object"]] = {}


def _group_for_language(language_code: str) -> list[str]:
    """Return the EasyOCR-compatible language group for *language_code*."""
    primary = (language_code or "en").lower().split("-")[0]
    return _LANGUAGE_TO_GROUP.get(primary, _LATIN_GROUP)


def _get_easyocr(language_code: str = "en"):
    """Lazily build (and cache) the EasyOCR reader for the requested language."""
    langs = _group_for_language(language_code)
    key = tuple(langs)

    if key not in _easyocr_readers:
        try:
            import easyocr
            _easyocr_readers[key] = easyocr.Reader(langs, gpu=False, verbose=False)
            log.info("EasyOCR reader initialised for languages: %s", langs)
        except Exception as err:
            log.error("EasyOCR init failed for languages %s: %s", langs, err)
            _easyocr_readers[key] = None

    return _easyocr_readers[key]


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


def extract_text(image_b64: str, language_code: str = "en") -> str:
    """
    Extract all text from a base64-encoded image.

    *language_code* selects which EasyOCR-compatible language group to use
    (see module docstring) — defaults to the Latin group (en/fr/de/es).

    Tries EasyOCR first, falls back to pytesseract.
    Returns an empty string if no text is found or if both engines fail.
    """
    if not image_b64:
        return ""

    img_array = _base64_to_numpy(image_b64)
    if img_array is None:
        return ""

    # ── EasyOCR ───────────────────────────────────────────────────────────────
    reader = _get_easyocr(language_code)
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
