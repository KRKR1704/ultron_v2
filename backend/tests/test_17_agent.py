"""
test_17_agent.py — Tests for core/agent.py run_agent().

Mocks brain.generate and tool executors to avoid real LLM/network calls.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.agent import run_agent, classify_intent
from core.memory import memory


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clear_session(session_id: str):
    memory.clear_session(session_id)


# ── run_agent() tests ─────────────────────────────────────────────────────────

async def test_agent_general_query_returns_response():
    """
    A general query (direct_answer intent) must call brain.generate and
    return its output.
    """
    session = "agent-test-general"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="The answer is 42, sir.")

        result = await run_agent(
            text="What is the meaning of life?",
            session_id=session,
            mode="professional",
            language_code="en",
        )

    assert result == "The answer is 42, sir."
    _clear_session(session)


async def test_agent_web_search_query_augments_prompt():
    """
    A web_search intent must call the search tool and pass its result
    to brain.generate as an augmented prompt.
    """
    session = "agent-test-search"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain, \
         patch("tools.web_search.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "Python tutorials can be found at python.org."
        mock_brain.generate = AsyncMock(return_value="Here are some Python resources, sir.")

        result = await run_agent(
            text="search for python tutorials",
            session_id=session,
            mode="professional",
            language_code="en",
        )

    assert isinstance(result, str)
    # brain.generate must have been called with the augmented prompt
    call_kwargs = mock_brain.generate.call_args
    prompt_used = call_kwargs[1].get("prompt") or call_kwargs[0][0]
    assert "python.org" in prompt_used or "tool result" in prompt_used.lower()
    _clear_session(session)


async def test_agent_adds_to_memory_after_response():
    """
    After run_agent returns, the session must contain the user message
    and assistant response in memory (stored by brain.generate).
    """
    session = "agent-memory-check-test"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="Understood, sir.")
        # brain.generate also calls memory.add_message internally;
        # here we call the real memory to verify integration
        mock_brain.generate.side_effect = _memory_storing_side_effect(
            session, "Hello.", "Understood, sir."
        )

        await run_agent(
            text="Hello.",
            session_id=session,
            mode="professional",
            language_code="en",
        )

    history = memory.get_history(session)
    assert any(m["role"] == "user" for m in history)
    _clear_session(session)


def _memory_storing_side_effect(session_id, user_text, response_text):
    """Helper that stores messages in real memory AND returns the response."""
    async def _side_effect(*args, **kwargs):
        memory.add_message(session_id, "user", user_text)
        memory.add_message(session_id, "assistant", response_text)
        return response_text
    return _side_effect


async def test_agent_uses_correct_mode_in_prompt():
    """
    run_agent must pass the mode to brain.generate so the correct
    personality is applied.
    """
    session = "agent-mode-test"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="Sure, dude!")

        await run_agent(
            text="tell me a joke",
            session_id=session,
            mode="casual",
            language_code="en",
        )

    call_kwargs = mock_brain.generate.call_args
    mode_used = call_kwargs[1].get("mode") or (
        call_kwargs[0][2] if len(call_kwargs[0]) > 2 else None
    )
    assert mode_used == "casual"
    _clear_session(session)


async def test_agent_language_code_passed_to_brain():
    """
    The language_code argument must be forwarded to brain.generate.
    """
    session = "agent-lang-test"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="Understood.")

        await run_agent(
            text="What time is it?",
            session_id=session,
            mode="professional",
            language_code="ja",
        )

    call_kwargs = mock_brain.generate.call_args
    lang_used = call_kwargs[1].get("language_code") or (
        call_kwargs[0][3] if len(call_kwargs[0]) > 3 else None
    )
    assert lang_used == "ja"
    _clear_session(session)


async def test_agent_smart_home_intent_calls_executor():
    """
    'turn on the lights' must trigger the smart_home executor and pass
    the tool result to brain.generate.
    """
    session = "agent-smarthome-test"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain, \
         patch("tools.smart_home.smart_home") as mock_sh:
        mock_sh.execute = AsyncMock(return_value="Bedroom has been turned on.")
        mock_brain.generate = AsyncMock(return_value="Done, the bedroom lights are on, sir.")

        result = await run_agent(
            text="turn on the bedroom lights",
            session_id=session,
            mode="professional",
            language_code="en",
        )

    assert isinstance(result, str)
    # Tool executor must have been called
    mock_sh.execute.assert_called_once()
    _clear_session(session)


async def test_agent_tool_failure_does_not_raise():
    """
    If a tool executor raises, run_agent must catch the exception and still
    call brain.generate with an error note in the prompt.
    """
    session = "agent-tool-failure"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain, \
         patch("tools.smart_home.smart_home") as mock_sh:
        mock_sh.execute = AsyncMock(side_effect=RuntimeError("HA is down"))
        mock_brain.generate = AsyncMock(return_value="I encountered an issue, sir.")

        result = await run_agent(
            text="turn on the lights",
            session_id=session,
        )

    assert isinstance(result, str)
    # brain.generate must still have been called
    mock_brain.generate.assert_called_once()
    _clear_session(session)


async def test_agent_returns_string_type():
    """run_agent must always return a str."""
    session = "agent-return-type"
    _clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="Response text.")

        result = await run_agent("hello", session_id=session)

    assert isinstance(result, str)
    _clear_session(session)
