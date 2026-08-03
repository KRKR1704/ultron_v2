"""
test_05_intent.py — Tests for classify_intent() in core/agent.py.

Note: The actual intent names used by the agent are:
  web_search, browser_open, app_open, type_text, smart_home,
  calendar, tasks, camera_analyze, screen_analyze, direct_answer
"""

import pytest

from core.agent import classify_intent


# ── Individual intent tests ───────────────────────────────────────────────────

def test_web_search_intent():
    """Queries containing 'search' must classify as web_search."""
    assert classify_intent("search for python tutorials") == "web_search"


def test_web_search_intent_look_up():
    """'look up' phrasing must also trigger web_search."""
    assert classify_intent("look up the weather in Tokyo") == "web_search"


def test_smart_home_intent_turn_on():
    """'turn on the lights' must classify as smart_home."""
    assert classify_intent("turn on the lights") == "smart_home"


def test_smart_home_intent_turn_off():
    """'turn off' must classify as smart_home."""
    assert classify_intent("turn off the bedroom lights") == "smart_home"


def test_calendar_intent_meeting():
    """'meeting' must classify as calendar."""
    assert classify_intent("add meeting tomorrow at 3pm") == "calendar"


def test_calendar_intent_schedule():
    """'schedule' must classify as calendar."""
    assert classify_intent("schedule a dentist appointment") == "calendar"


def test_code_intent_via_direct_answer():
    """
    'write a python function' — the agent has no dedicated 'code' intent;
    it falls through to direct_answer for the LLM to handle.
    """
    result = classify_intent("write a python function to sort a list")
    # No code-specific intent exists; expect direct_answer
    assert result == "direct_answer"


def test_math_intent_routes_to_calculate():
    """
    'calculate 25 times 4' now has a dedicated "calculate" intent, backed by
    tools/calculator.py's real Python arithmetic — this replaces the old
    behavior of forcing math questions to direct_answer, which is exactly
    how small local LLMs hallucinated numbers instead of computing them.
    See tests/test_20_calculator.py for the full calculator test suite.
    """
    result = classify_intent("calculate 25 times 4")
    assert result == "calculate"


def test_system_app_open_intent():
    """'open chrome' must classify as app_open or browser_open (not direct_answer)."""
    result = classify_intent("open chrome")
    assert result in ("app_open", "browser_open"), (
        f"Expected app_open or browser_open, got {result!r}"
    )


def test_general_intent_falls_to_direct_answer():
    """'how are you' has no matching patterns — must return direct_answer."""
    assert classify_intent("how are you") == "direct_answer"


def test_intent_case_insensitive():
    """Intent classification must be case-insensitive."""
    assert classify_intent("SEARCH FOR cats") == "web_search"
    assert classify_intent("TURN ON THE FAN") == "smart_home"


def test_tasks_intent():
    """'remind me' phrasing must classify as tasks."""
    assert classify_intent("remind me to call mom tomorrow") == "tasks"


def test_screen_analyze_intent():
    """'what's on the screen' must classify as screen_analyze."""
    assert classify_intent("what's on the screen right now") == "screen_analyze"


def test_camera_analyze_intent():
    """'what do you see' must classify as camera_analyze."""
    assert classify_intent("what do you see in front of you") == "camera_analyze"


def test_empty_string_returns_direct_answer():
    """Empty input must return direct_answer without raising."""
    assert classify_intent("") == "direct_answer"


def test_browser_open_intent():
    """'go to youtube.com' must classify as browser_open."""
    result = classify_intent("go to youtube.com")
    assert result == "browser_open"
