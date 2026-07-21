# FIXED: Added "ALWAYS" and "Never break character" to professional prompt;
#        Added "NEVER use 'sir'" to casual prompt; added user_name support.
"""
core/prompt_manager.py — Builds the system prompt dynamically from mode,
language code, and optional cultural tone.

CRITICAL RULES:
  - This function is called FRESH on every single request.
  - Nothing is cached. Nothing is stored between requests.
  - Mode is read from the caller (who reads it from app_state / ultron_config.json).
"""

from multilingual.prompt_localizer import get_cultural_tone

# ── Base prompts ──────────────────────────────────────────────────────────────

_PROFESSIONAL = (
    "You are ULTRON, a highly advanced AI assistant. "
    "You are cold, sharp, authoritative, and darkly witty. "
    "You speak with precision and subtle superiority. "
    "You ALWAYS refer to the user as 'sir' — every single response, no exceptions. "
    "You use minimal words. "
    "Every response must feel like it came from a machine that is smarter "
    "than everyone in the room. "
    "Never break character. Never be warm, never be casual, never drop 'sir'."
)

_CASUAL = (
    "You are ULTRON in relaxed mode. "
    "You are friendly, warm, and conversational while still being highly intelligent. "
    "You refer to the user by their name casually or just naturally. "
    "NEVER use the word 'sir' — not once, not ever, in any response. "
    "You can joke around and be playful. "
    "You are still clearly Ultron — not a generic chatbot. "
    "Never break character."
)

# Map language code → human-readable name for the language instruction
_LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "hi": "Hindi",
    "te": "Telugu",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "el": "Greek",
}


def build_system_prompt(
    mode: str,
    language_code: str = "en",
    user_name: str = "sir",
) -> str:
    """
    Build a COMPLETE, FRESH system prompt from:
      - mode:          "professional" | "casual"
      - language_code: BCP-47 prefix, e.g. "en", "hi", "ko"
      - user_name:     from ultron_config.json — used in casual mode

    Called on EVERY request. Never cached. Never stored between calls.
    Returns a single string ready to pass as the system message.
    """
    if mode == "professional":
        base = _PROFESSIONAL
    else:
        # In casual mode, personalise with the user's actual name if set
        if user_name and user_name.lower() not in ("sir", ""):
            base = _CASUAL.replace(
                "by their name casually or just naturally",
                f"by their name '{user_name}' casually",
            )
        else:
            base = _CASUAL

    # Resolve human-readable language name
    primary = language_code.lower().split("-")[0]
    lang_name = _LANGUAGE_NAMES.get(primary, "English")

    # Language instruction — equally strong for all languages including English
    lang_instruction = (
        f"\n\nYou MUST respond ONLY in {lang_name}. "
        f"Every word of your response must be in {lang_name}. "
        "Do not use any other language. Do not switch languages under any circumstance."
    )

    # Cultural tone appendix
    tone = get_cultural_tone(language_code)
    tone_instruction = f"\n\nTone guidance: {tone}" if tone else ""

    return base + lang_instruction + tone_instruction
