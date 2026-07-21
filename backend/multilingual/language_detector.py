# FIXED: Added detect_language_from_text() using langdetect for text-based
#        language detection (used by /chat when there's no STT output).
"""
multilingual/language_detector.py — Parse and normalise language codes.

faster-whisper returns a full language name (e.g. "english", "hindi") or a
short BCP-47 code.  This module normalises everything to lowercase 2-letter
ISO 639-1 codes (e.g. "en", "hi", "ko").

Also provides detect_language_from_text() for text-chat requests where there
is no Whisper STT output to read the language from.
"""

import logging

log = logging.getLogger(__name__)

# Mapping from Whisper's full-name strings to ISO 639-1 codes
_WHISPER_NAME_TO_CODE: dict[str, str] = {
    "english":    "en",
    "hindi":      "hi",
    "telugu":     "te",
    "japanese":   "ja",
    "korean":     "ko",
    "chinese":    "zh",
    "spanish":    "es",
    "french":     "fr",
    "german":     "de",
    "arabic":     "ar",
    "portuguese": "pt",
    "italian":    "it",
    "russian":    "ru",
    "dutch":      "nl",
    "polish":     "pl",
    "turkish":    "tr",
    "swedish":    "sv",
    "norwegian":  "no",
    "danish":     "da",
    "finnish":    "fi",
    "greek":      "el",
    "czech":      "cs",
    "romanian":   "ro",
    "hungarian":  "hu",
    "thai":       "th",
    "vietnamese": "vi",
    "indonesian": "id",
    "malay":      "ms",
    "tagalog":    "tl",
}

# Supported language codes — used to validate langdetect output
_SUPPORTED_CODES = set(_WHISPER_NAME_TO_CODE.values()) | {"en"}


def normalise_language_code(raw: str) -> str:
    """
    Convert a raw Whisper language string (full name or code) to a lowercase
    ISO 639-1 code.  Returns "en" if the input cannot be mapped.
    """
    if not raw:
        return "en"

    cleaned = raw.lower().strip()

    # Already a short code (1-3 chars)
    if len(cleaned) <= 3 and cleaned.isalpha():
        return cleaned

    # Full-name lookup
    return _WHISPER_NAME_TO_CODE.get(cleaned, "en")


def get_language_name(language_code: str) -> str:
    """Return a human-readable language name for a 2-letter code."""
    _CODE_TO_NAME = {v: k.capitalize() for k, v in _WHISPER_NAME_TO_CODE.items()}
    _CODE_TO_NAME["en"] = "English"
    return _CODE_TO_NAME.get(language_code.lower(), "English")


def detect_language_from_text(text: str) -> str:
    """
    Detect the language of plain text input using langdetect.

    Used by the /chat endpoint so that text-mode conversations also get the
    correct language code for TTS routing and LLM instructions.

    Returns an ISO 639-1 code (e.g. "en", "hi", "ko").
    Falls back to "en" on any error or if the text is too short.
    """
    if not text or len(text.strip()) < 4:
        return "en"

    try:
        from langdetect import detect, DetectorFactory
        # Make detection deterministic
        DetectorFactory.seed = 0
        code = detect(text.strip())
        # Map to 2-letter primary subtag
        primary = code.lower().split("-")[0]
        # Validate against known codes; default to "en" for unknown
        if primary in _SUPPORTED_CODES:
            return primary
        # Some langdetect codes are 2-letter but not in our map — pass through
        if len(primary) == 2 and primary.isalpha():
            return primary
        return "en"
    except ImportError:
        # langdetect not installed — graceful fallback
        log.debug("langdetect not installed; defaulting language to 'en'.")
        return "en"
    except Exception as err:
        log.debug("Language detection failed: %s — defaulting to 'en'.", err)
        return "en"
