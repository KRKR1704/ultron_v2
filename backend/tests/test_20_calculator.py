"""
test_20_calculator.py — Tests for tools/calculator.py and its wiring into
the agent's "calculate" intent (core/agent.py, api/routes/chat.py).

The core regression this file guards against: a real production bug where
the same math question sent to /chat three times produced three different
WRONG answers, because the LLM was "answering" arithmetic itself instead of
a real calculator computing it. tools/calculator.py fixes this with a real,
whitelisted Python evaluator (never eval()) — the LLM only narrates the
pre-computed result, and its narration is verified and overridden with a
guaranteed-correct template if it drifts from the real number (see
core/agent.py's _run_calculate_and_narrate).
"""

from unittest.mock import AsyncMock, patch

import pytest

from main import app_state
from tools.calculator import calculate, extract_math_expression
from core.agent import classify_intent


def _post_chat(client, message: str, session_id: str = "calc-test"):
    return client.post("/chat", json={"message": message, "session_id": session_id})


# ── 1. Basic arithmetic — real /chat integration ──────────────────────────────

def test_basic_arithmetic(client):
    """
    'what is 1000+290/22' must return the EXACT correct result — order of
    operations means division happens before addition: 290/22 = 13.181818...,
    +1000 = 1013.181818. The mocked LLM's narration deliberately contains no
    number at all, proving the real computed value (not an LLM guess) is
    what ends up in the response, via the guaranteed-correct fallback.
    """
    app_state["config"]["mode"] = "professional"

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="Here you go, sir.")
        mock_tts.return_value = ""

        response = _post_chat(client, "what is 1000+290/22")

    assert response.status_code == 200
    data = response.json()
    assert "1013.181818" in data["response_text"]


# ── 2. Multiple operators — direct calculator checks ──────────────────────────

def test_multiple_operators():
    """A few more expressions where order of operations must be respected."""
    r1 = calculate(extract_math_expression("what is 5 * 3 + 2"))
    assert r1["success"] is True
    assert r1["result"] == 17

    r2 = calculate(extract_math_expression("what is 100 / 4 - 5"))
    assert r2["success"] is True
    assert r2["result"] == 20

    r3 = calculate(extract_math_expression("what is (3+4)*2"))
    assert r3["success"] is True
    assert r3["result"] == 14


# ── 3. Division by zero — graceful error, no crash, no fabricated number ─────

def test_division_by_zero(client):
    """'what is 5 / 0' must return a graceful error — the LLM must never
    even be invoked for a failed computation, since there's no real number
    to narrate."""
    app_state["config"]["mode"] = "professional"

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(return_value="should not be called")
        mock_tts.return_value = ""

        response = _post_chat(client, "what is 5 / 0")

    assert response.status_code == 200
    data = response.json()
    assert "division by zero" in data["response_text"].lower()
    mock_brain.generate.assert_not_called()


# ── 4. Word-based math — order of operations must still be respected ────────

def test_word_based_math():
    """'what is 5 plus 3 times 2' must parse to 5+3*2 and respect order of
    operations: 5+(3*2)=11, not (5+3)*2=16."""
    expr = extract_math_expression("what is 5 plus 3 times 2")
    assert expr == "5+3*2"
    result = calculate(expr)
    assert result["success"] is True
    assert result["result"] == 11


# ── 5. Math functions ──────────────────────────────────────────────────────────

def test_math_functions():
    """'square root of 144' -> 12, 'factorial of 5' -> 120."""
    r1 = calculate(extract_math_expression("square root of 144"))
    assert r1["success"] is True
    assert r1["result"] == 12

    r2 = calculate(extract_math_expression("factorial of 5"))
    assert r2["success"] is True
    assert r2["result"] == 120


# ── 6. THE core regression test ───────────────────────────────────────────────

def test_repeated_same_question_consistent(client):
    """
    Mirrors the actual bug report: the exact same math question sent 3 times
    used to produce 3 different WRONG answers. Here the mocked LLM behaves
    the way the buggy one did — a different (always wrong) number every time
    it's asked to narrate — yet all 3 /chat responses must still contain the
    SAME correct number, because the real calculator result overrides the
    LLM's drift every time via the verified-fallback mechanism.
    """
    app_state["config"]["mode"] = "professional"
    call_count = {"n": 0}

    async def flaky_narration(*args, **kwargs):
        call_count["n"] += 1
        # Always wrong, always different, and — being a multiple of 137 —
        # can never coincidentally equal the real result (1013.181818).
        return f"The answer is {call_count['n'] * 137}, sir."

    with patch("core.agent.brain") as mock_brain, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_brain.generate = AsyncMock(side_effect=flaky_narration)
        mock_tts.return_value = ""

        responses = [
            _post_chat(client, "what is 1000+290/22", session_id="consistency-check")
            for _ in range(3)
        ]

    texts = [r.json()["response_text"] for r in responses]

    for t in texts:
        assert "1013.181818" in t, f"Expected the real result in every response, got: {t!r}"
    assert len(set(texts)) == 1, f"Responses were inconsistent across identical requests: {texts!r}"


# ── 7. Non-math questions must be unaffected ──────────────────────────────────

def test_non_math_question_unaffected():
    """'what is the capital of France' must NOT be routed to the calculator —
    it has no digits/operator to extract, so it still falls to direct_answer."""
    assert classify_intent("what is the capital of France") == "direct_answer"
    assert extract_math_expression("what is the capital of France") is None


# ── 8. Phone numbers / dates must not be misclassified as math ──────────────

def test_ambiguous_math_adjacent_text():
    """
    Phone numbers ("555-1234") and dates ("3/15") share the same superficial
    "digits + operator + digits" shape as arithmetic but must not be
    misclassified as the calculate intent.
    """
    assert classify_intent("call me at 555-1234") != "calculate"
    assert classify_intent("meeting on 3/15") == "calendar"
    assert extract_math_expression("call me at 555-1234") is None
    assert extract_math_expression("meeting on 3/15") is None
