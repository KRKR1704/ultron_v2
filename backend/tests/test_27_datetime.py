"""
test_27_datetime.py — Tests for the "datetime" skill: real current date/time
(local system clock) and relative day-count calculations, computed by Python
— never guessed by the LLM.

Mirrors test_20_calculator.py's structure and mocking pattern, since
_run_datetime_and_narrate (core/agent.py) is the same anti-hallucination
shape as _run_calculate_and_narrate: real Python computes the fact, the LLM
only narrates it, and its narration is verified and overridden with a
guaranteed-correct template if it drifts.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from core.agent import classify_intent
from core.prompt_manager import build_system_prompt
from tools.datetime_tool import days_until, extract_days_until_target, get_current_datetime_fact


def _post_chat(client, message: str, session_id: str = "datetime-test"):
    return client.post("/chat", json={"message": message, "session_id": session_id})


# ── 1. Intent classification ───────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "what is today's date",
    "what's today's date",
    "what time is it",
    "what day is it",
    "current time please",
    "what's the current date",
    "how many days until Friday",
    "tell me the time",
])
def test_datetime_intent_classification(text):
    assert classify_intent(text) == "datetime"


def test_datetime_checked_before_web_search_for_current_time_phrasing():
    """
    web_search.SKILL.md has '\\bwhat is the (current|latest|recent|today's|
    live)\\b', which would otherwise swallow 'what is the current time' —
    datetime's lower priority (5 vs web_search's 10) must win.
    """
    assert classify_intent("what is the current time") == "datetime"
    assert classify_intent("what is the current date") == "datetime"
    # web_search must still work for genuinely current-events phrasing.
    assert classify_intent("what is the latest news on AI") == "web_search"


# ── 2. False-positive guard: romantic "date" must never trigger this skill ──────

@pytest.mark.parametrize("text", [
    "I have a date tonight",
    "I'm going on a date this weekend",
    "she asked me on a date",
    "my date is running late",
])
def test_datetime_skill_does_not_misfire_on_romantic_date(text):
    assert classify_intent(text) != "datetime"


# ── 3. Multilingual (at least 2 non-English languages) ─────────────────────────

def test_spanish_current_time():
    assert classify_intent("¿Qué hora es?") == "datetime"


def test_spanish_current_date():
    assert classify_intent("¿Cuál es la fecha de hoy?") == "datetime"


def test_french_current_time():
    assert classify_intent("Quelle heure est-il ?") == "datetime"


def test_german_current_date():
    assert classify_intent("Welcher Tag ist heute?") == "datetime"


def test_hindi_current_date():
    assert classify_intent("आज की तारीख क्या है") == "datetime"


def test_japanese_current_time():
    assert classify_intent("今何時ですか") == "datetime"


# ── 4. tools/datetime_tool.py — direct unit tests ───────────────────────────────

def test_get_current_datetime_fact_matches_real_clock():
    fact, anchors = get_current_datetime_fact()
    now = datetime.now()
    assert str(now.year) in anchors
    assert str(now.day) in anchors
    assert now.strftime("%B") in fact  # month name present
    assert str(now.year) in fact


def test_extract_days_until_target():
    assert extract_days_until_target("how many days until Friday") == "Friday"
    assert extract_days_until_target("days until Christmas") == "Christmas"
    assert extract_days_until_target("what time is it") is None


def test_days_until_computes_real_difference():
    now = datetime(2026, 8, 6)  # a Thursday
    result = days_until("Friday", now=now)
    assert result["success"] is True
    assert result["days"] == 1


def test_days_until_unparseable_target_graceful_error():
    result = days_until("asdkjaslkdj laksjdlk")
    assert result["success"] is False
    assert result["error"] is not None


# ── 5. Real /chat integration — grounding safeguard ─────────────────────────────

def test_current_date_response_contains_real_date_via_llm_that_omits_it(client):
    """
    Mirrors test_20_calculator.py's core regression test: the mocked LLM
    narration deliberately contains NO date info at all, proving the real
    computed fact (not an LLM guess) is what ends up in the response, via
    the guaranteed-correct fallback template.
    """
    from main import app_state
    app_state["config"]["mode"] = "professional"
    now = datetime.now()

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="I'm not sure, sir.")
        mock_tts.return_value = ""

        response = _post_chat(client, "what is today's date")

    assert response.status_code == 200
    data = response.json()
    assert str(now.year) in data["response_text"]
    assert str(now.day) in data["response_text"]
    mock_brain.generate.assert_called()  # LLM was tried (and retried) before fallback


def test_current_time_response_grounded_llm_narration_accepted(client):
    """When the LLM's narration DOES include the grounding anchors, it's
    used verbatim — no unnecessary retry/fallback."""
    from main import app_state
    app_state["config"]["mode"] = "professional"
    fact, anchors = get_current_datetime_fact()

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(
            return_value=f"It is currently {fact}, sir."
        )
        mock_tts.return_value = ""

        response = _post_chat(client, "what time is it")

    assert response.status_code == 200
    data = response.json()
    for anchor in anchors:
        assert anchor in data["response_text"]
    assert mock_brain.generate.call_count == 1  # accepted on first try, no retry needed


def test_repeated_same_datetime_question_consistent(client):
    """
    Same shape as test_20_calculator.py's flaky-LLM consistency test: the
    mocked LLM gives a different (always ungrounded) answer every time, yet
    every /chat response must still contain the same real date, because the
    verified-fallback mechanism overrides the LLM's drift every time.
    """
    from main import app_state
    app_state["config"]["mode"] = "professional"
    now = datetime.now()
    call_count = {"n": 0}

    async def flaky_narration(*args, **kwargs):
        call_count["n"] += 1
        return f"I believe it's day {call_count['n']} of something, sir."

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(side_effect=flaky_narration)
        mock_tts.return_value = ""

        responses = [
            _post_chat(client, "what is today's date", session_id="datetime-consistency")
            for _ in range(3)
        ]

    texts = [r.json()["response_text"] for r in responses]
    for t in texts:
        assert str(now.year) in t
        assert str(now.day) in t


def test_days_until_friday_via_chat_uses_real_computation(client):
    """
    The grounding anchors are digits from the TARGET date (year, day-of-
    month) — not the days-count itself — because the natural "today, .../
    tomorrow, ..." phrasing for a 0/1-day gap never states that count as a
    literal digit, which would otherwise break the "guaranteed correct"
    fallback template for exactly those two cases.
    """
    from main import app_state
    app_state["config"]["mode"] = "professional"

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Not sure, sir.")
        mock_tts.return_value = ""

        response = _post_chat(client, "how many days until Friday")

    assert response.status_code == 200
    data = response.json()
    real = days_until("Friday")
    for anchor in real["anchors"]:
        assert anchor in data["response_text"]


# ── 6. System prompt injection (Approach 1) ─────────────────────────────────────

def test_system_prompt_includes_real_current_date():
    now = datetime.now()
    prompt = build_system_prompt("professional", "en", "sir")
    assert str(now.year) in prompt
    assert now.strftime("%B") in prompt
    assert "current date and time:" in prompt.lower()
    # The prompt explicitly forbids the refusal — it's fine for the negation
    # instruction itself to mention it ("never claim you don't have access
    # ... you do"); what matters is Ultron is never told it lacks the date.
    assert "you do." in prompt.lower()


def test_system_prompt_datetime_present_in_both_modes():
    now = datetime.now()
    for mode in ("professional", "casual"):
        prompt = build_system_prompt(mode, "en", "sir")
        assert str(now.year) in prompt


# ── 7. Unrelated intents unaffected ──────────────────────────────────────────────

def test_calendar_intent_still_unaffected_by_datetime_skill():
    """'meeting on 3/15' must still classify as calendar, not datetime."""
    assert classify_intent("meeting on 3/15") == "calendar"


def test_math_with_date_like_text_still_unaffected():
    assert classify_intent("what is 5 plus 3") == "calculate"
