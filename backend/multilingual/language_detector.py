"""
multilingual/language_detector.py — Parse and normalise language codes.

faster-whisper returns a full language name (e.g. "english", "hindi") or a
short BCP-47 code.  This module normalises everything to lowercase 2-letter
ISO 639-1 codes (e.g. "en", "hi", "ko").

Also provides detect_language_from_text() for text-chat requests where there
is no Whisper STT output to read the language from. `langdetect` is well
known to be unreliable on short strings — and NOT merely "low confidence"
unreliable: it is often *extremely* (>99%) confident and *wrong* on short
Latin-alphabet phrases (e.g. "greet me" scores 99.99% Dutch, "open
calculator" scores 99.9999% Romanian, "ok" scores 99.99% Slovak). A
confidence-score threshold alone cannot catch this. Detection here is
therefore layered:
  1. Script-level detection first: non-Latin scripts (Devanagari, Telugu,
     Hangul, Japanese kana, Arabic) are an unambiguous signal regardless of
     length — a Devanagari character is never accidentally English.
  2. Only for plain Latin-alphabet text does length + langdetect confidence
     apply, since that's where the short-text misdetection problem above
     actually lives (distinguishing en/es/fr short phrases from each other).
  3. Below the confidence/length bar, fall back to the session's own
     last-known language instead of a fresh (and often wrong) guess.
"""

import logging
import re
from threading import Lock

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

# Supported language codes — used to validate langdetect output (STT path)
_SUPPORTED_CODES = set(_WHISPER_NAME_TO_CODE.values()) | {"en"}

# ── Text-chat language detection tuning ──────────────────────────────────────

# Languages ULTRON actually knows how to speak/respond in for text chat
# (per core/prompt_manager.py's cultural-tone map and the TTS routing table).
# A confidently-detected language outside this set still falls back to
# English rather than attempting a response in an unsupported language.
_TEXT_SUPPORTED_LANGUAGES = {"en", "hi", "es", "fr", "te", "ko", "ja", "zh", "ar"}

# Below this length, langdetect's guess on LATIN-ALPHABET text is not
# trustworthy enough to act on — short casual phrases ("greet me", "ok",
# "open calculator") get misdetected as random languages far too often.
# Rely on session continuity instead. This does NOT apply to text caught by
# the script-level check below, which is reliable at any length.
_MIN_CONFIDENT_LENGTH = 20

# Minimum langdetect confidence (from detect_langs()) required to actually
# switch the session's language. Below this, stay on the session's current
# language rather than switching on a low-confidence guess. Note this alone
# is NOT sufficient protection against short-text misdetection — langdetect
# routinely reports >99% confidence for a *wrong* short-text guess — which is
# exactly why the length floor above exists as a separate, additional gate.
_CONFIDENCE_THRESHOLD = 0.85

# ── Script-level detection ────────────────────────────────────────────────────
# Unicode ranges for the non-Latin scripts among ULTRON's supported languages.
# Presence of any of these characters is a far stronger, length-independent
# signal than langdetect's statistical model — a Devanagari character is
# never accidentally English. Order matters: Japanese kana (hiragana/
# katakana) is checked before Chinese, because CJK ideographs (Kanji) are
# shared with Japanese — a Japanese sentence containing Kanji almost always
# also contains kana, so checking kana first avoids misreading Japanese as
# Chinese.
_SCRIPT_PATTERNS: list[tuple[str, "re.Pattern[str]"]] = [
    ("hi", re.compile(r"[ऀ-ॿ]")),   # Devanagari (Hindi)
    ("te", re.compile(r"[ఀ-౿]")),   # Telugu
    ("ko", re.compile(r"[가-힣]")),   # Hangul syllables (Korean)
    ("ar", re.compile(r"[؀-ۿ]")),   # Arabic
    ("ja", re.compile(r"[぀-ヿ]")),   # Hiragana + Katakana (Japanese)
    ("zh", re.compile(r"[一-鿿]")),   # CJK Unified Ideographs (Chinese)
]


def _detect_script_language(text: str) -> str | None:
    """
    Return a supported language code if *text* contains characters from one
    of its distinctive (non-Latin) scripts, else None.

    This check works on text of any length, including a single character —
    unlike statistical detection, script membership isn't a probability.
    """
    for code, pattern in _SCRIPT_PATTERNS:
        if pattern.search(text):
            return code
    return None

# Per-session "last confidently-detected language" — a short follow-up like
# "ok" after a Hindi message should stay in Hindi, not reset to English.
_session_lock = Lock()
_session_last_language: dict[str, str] = {}


def _get_session_language(session_id: str) -> str | None:
    with _session_lock:
        return _session_last_language.get(session_id)


def _set_session_language(session_id: str, language_code: str) -> None:
    with _session_lock:
        # Crude unbounded-growth guard — a single-user desktop assistant will
        # never realistically approach this, but never say never.
        if len(_session_last_language) > 10_000:
            _session_last_language.clear()
        _session_last_language[session_id] = language_code


def clear_session_language(session_id: str) -> None:
    """Forget the session's last-detected language (e.g. on session reset)."""
    with _session_lock:
        _session_last_language.pop(session_id, None)


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


def detect_language_from_text(text: str, session_id: str = "default") -> str:
    """
    Detect the language of plain text input using langdetect, biased toward
    conversational continuity within *session_id*.

    Used by the /chat and /ws endpoints so that text-mode conversations also
    get a language code for TTS routing and LLM instructions.

    Rules (in order):
      1. Empty input — stay on whatever language this session was last
         speaking (or "en" if this is the first message in the session).
      2. Script-level check: non-Latin scripts (Hindi, Telugu, Korean,
         Japanese, Arabic) are detected directly from the characters
         present, at ANY length — this is what lets a short Hindi reply
         switch languages correctly without needing 20+ characters.
      3. For plain Latin-alphabet text: shorter than `_MIN_CONFIDENT_LENGTH`
         chars is too short for langdetect to be trustworthy — stay on the
         session's current language rather than guess.
      4. langdetect's top candidate (via `detect_langs()`, which exposes a
         confidence score) must clear `_CONFIDENCE_THRESHOLD` to be trusted
         at all — a low-confidence guess also falls back to the session's
         current language rather than switching.
      5. A confident guess outside `_TEXT_SUPPORTED_LANGUAGES` (a language
         ULTRON doesn't actually have tone/TTS support for) falls back to
         English rather than trying to respond in it.
      6. Anything else (missing dependency, detector error) also falls back
         to the session's current language.

    Every path updates the session's last-known language before returning,
    so the next short follow-up in the same session inherits it.

    Returns an ISO 639-1 code (e.g. "en", "hi", "ko").
    """
    stripped = (text or "").strip()
    previous = _get_session_language(session_id)

    if not stripped:
        result = previous or "en"
        _set_session_language(session_id, result)
        return result

    script_lang = _detect_script_language(stripped)
    if script_lang is not None:
        _set_session_language(session_id, script_lang)
        return script_lang

    if len(stripped) < _MIN_CONFIDENT_LENGTH:
        result = previous or "en"
        _set_session_language(session_id, result)
        return result

    try:
        from langdetect import detect_langs, DetectorFactory
        # Make detection deterministic
        DetectorFactory.seed = 0

        candidates = detect_langs(stripped)
        top = candidates[0]
        primary = top.lang.lower().split("-")[0]

        if top.prob < _CONFIDENCE_THRESHOLD:
            # Not confident enough to switch languages mid-conversation.
            log.debug(
                "Language detection low-confidence (%.2f < %.2f) for %r — "
                "keeping session language.",
                top.prob, _CONFIDENCE_THRESHOLD, stripped[:50],
            )
            result = previous or "en"
        elif primary not in _TEXT_SUPPORTED_LANGUAGES:
            # Confidently a language, but not one ULTRON can respond in.
            result = "en"
        else:
            result = primary

    except ImportError:
        # langdetect not installed — graceful fallback
        log.debug("langdetect not installed; defaulting language to 'en'.")
        result = previous or "en"
    except Exception as err:
        log.debug("Language detection failed: %s — defaulting to 'en'.", err)
        result = previous or "en"

    _set_session_language(session_id, result)
    return result
