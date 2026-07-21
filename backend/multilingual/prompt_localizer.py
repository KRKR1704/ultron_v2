"""
multilingual/prompt_localizer.py — Cultural tone adapter.

Maps a BCP-47 language code prefix to a short tone instruction that is
appended to the system prompt by prompt_manager.py.
"""

_TONE_MAP: dict[str, str] = {
    "en": "Be direct and witty. Standard Ultron energy.",
    "hi": "Be slightly more expressive and warm in tone while remaining authoritative.",
    "te": "Use a warm but sharp tone with a respectful undertone.",
    "ja": "Be extremely formal and precise. Use minimal words. Be stoic.",
    "ko": "Respect polite speech levels while maintaining dominance.",
    "zh": "Be composed and philosophical. Add a strategic edge to responses.",
    "es": "Be more dynamic and slightly dramatic in expression.",
    "fr": "Be intellectual and carry a slight air of condescension. Very Ultron.",
    "ar": "Be formal and eloquent. Use sophisticated language.",
    "de": "Be blunt, precise, and efficient. No filler words.",
    "pt": "Be warm but sharp. Balance friendliness with authority.",
    "it": "Be expressive and authoritative. Dramatic where appropriate.",
    "ru": "Be cold, composed, and strategic. Minimal emotion.",
}

_DEFAULT_TONE = "Be direct and witty. Standard Ultron energy."


def get_cultural_tone(language_code: str) -> str:
    """
    Return the tone instruction for *language_code*.

    Accepts full BCP-47 tags (e.g. "zh-TW", "es-MX") — uses only the
    primary subtag for lookup.  Returns the English default for unknown codes.
    """
    primary = language_code.lower().split("-")[0]
    return _TONE_MAP.get(primary, _DEFAULT_TONE)
