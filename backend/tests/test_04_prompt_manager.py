"""
test_04_prompt_manager.py — Tests for core/prompt_manager.py build_system_prompt().
"""

import pytest

from core.prompt_manager import build_system_prompt


_ALL_LANGUAGE_CODES = [
    "en", "hi", "te", "ja", "ko", "zh", "es", "fr", "de", "ar", "pt", "it", "ru",
]


def test_professional_mode_prompt_contains_keywords():
    """Professional mode prompt must convey precision and authority."""
    prompt = build_system_prompt("professional", "en")
    lower = prompt.lower()

    # At least one authoritative keyword must be present
    authoritative_terms = ["precision", "precise", "efficient", "sir", "sharp", "authoritative"]
    assert any(term in lower for term in authoritative_terms), (
        f"Professional prompt missing authority keywords. Got: {prompt[:200]}"
    )


def test_casual_mode_prompt_contains_keywords():
    """Casual mode prompt must convey a friendly, relaxed tone."""
    prompt = build_system_prompt("casual", "en")
    lower = prompt.lower()

    friendly_terms = ["chill", "friendly", "warm", "casual", "relax", "conversational"]
    assert any(term in lower for term in friendly_terms), (
        f"Casual prompt missing friendly keywords. Got: {prompt[:200]}"
    )


def test_language_instruction_included_for_non_english():
    """Non-English language codes must add an explicit language instruction."""
    prompt = build_system_prompt("professional", "hi")

    # Must include the language name (Hindi) and a directive to respond in it
    assert "Hindi" in prompt, "Hindi language name must appear in the prompt"
    assert "respond" in prompt.lower() or "hindi" in prompt.lower()


def test_english_needs_no_extra_language_instruction_beyond_base():
    """
    English prompts still include a language instruction (by design), but
    must not contain instructions for other languages.
    """
    prompt = build_system_prompt("professional", "en")

    # Must NOT instruct the model to respond in a non-English language
    for lang_name in ["Hindi", "Japanese", "Korean", "Chinese", "Spanish", "French"]:
        assert lang_name not in prompt, (
            f"English prompt should not contain instruction for {lang_name}"
        )


def test_all_supported_languages_generate_prompt():
    """
    Every supported language code must produce a non-empty string prompt
    without raising an exception.
    """
    for lang_code in _ALL_LANGUAGE_CODES:
        for mode in ("professional", "casual"):
            prompt = build_system_prompt(mode, lang_code)
            assert isinstance(prompt, str), (
                f"build_system_prompt returned non-string for {lang_code}/{mode}"
            )
            assert len(prompt) > 0, (
                f"build_system_prompt returned empty string for {lang_code}/{mode}"
            )


def test_prompt_is_string_and_nonempty():
    """Basic sanity: the return type is always a non-empty str."""
    for mode in ("professional", "casual"):
        result = build_system_prompt(mode)
        assert isinstance(result, str)
        assert len(result.strip()) > 0


def test_unknown_language_code_falls_back_gracefully():
    """An unknown language code must not raise and must return a valid prompt."""
    prompt = build_system_prompt("professional", "xx")
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_bcp47_full_tag_handled():
    """Full BCP-47 tags like 'zh-TW' or 'es-MX' must not raise."""
    for tag in ("zh-TW", "es-MX", "fr-CA", "pt-BR"):
        prompt = build_system_prompt("professional", tag)
        assert isinstance(prompt, str) and len(prompt) > 0
