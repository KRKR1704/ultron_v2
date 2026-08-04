"""
test_21_file_open.py — Tests for Bug 1: open_file() wiring (file_open intent).

tools.app_control.open_file() was a complete, working implementation with
no intent pattern routing to it and no API route exposing it — completely
unreachable through the product. This file verifies:
  - classify_intent() now recognizes file/folder-opening phrasing as its own
    "file_open" intent, distinct from app_open and browser_open.
  - No regression: "open Spotify" still classifies as app_open, "open
    github.com" still classifies as browser_open.
  - The full pipeline (classify -> executor -> tool) actually opens a real,
    reliably-existing folder (the user's Documents folder) — not mocked.
  - A nonexistent file produces a graceful, tool-grounded error string, not
    a crash and not an LLM-fabricated fake success (same anti-hallucination
    pattern already used for app_open).
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from core.agent import classify_intent, run_agent, _run_file_open
from core.memory import memory


# ── classify_intent() ─────────────────────────────────────────────────────────

def test_file_open_downloads_folder_classifies_correctly():
    assert classify_intent("open my downloads folder") == "file_open"


def test_file_open_documents_folder_classifies_correctly():
    assert classify_intent("open my documents folder") == "file_open"


def test_file_open_named_file_classifies_correctly():
    assert classify_intent("open the file report.pdf") == "file_open"
    assert classify_intent("show me the file notes.txt") == "file_open"
    assert classify_intent("open resume.docx") == "file_open"


# ── Regression: app_open / browser_open must still win for their own cases ────

def test_app_open_not_misrouted_to_file_open():
    """'open Spotify' must still classify as app_open, never file_open."""
    result = classify_intent("open Spotify")
    assert result == "app_open"


def test_browser_open_not_misrouted_to_file_open():
    """'open github.com' must still classify as browser_open, never file_open."""
    result = classify_intent("open github.com")
    assert result == "browser_open"


# ── Real, unmocked execution ──────────────────────────────────────────────────

def test_real_documents_folder_opens_without_error():
    """
    Full pipeline: a real, reliably-existing folder (the user's Documents
    directory) must actually open via os.startfile/open/xdg-open — no mocks.
    Uses Documents rather than a specific file so the test doesn't depend on
    any file existing beyond what every OS install already has.
    """
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        _run_file_open("open my documents folder")
    )
    assert result.startswith("Opening"), f"Expected a real success message, got: {result!r}"
    assert "not found" not in result.lower()
    assert "could not" not in result.lower()


def test_nonexistent_file_returns_graceful_error_not_crash():
    """
    Opening a file that doesn't exist must return a real, tool-grounded
    error string (never raise, never a fabricated success).
    """
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(
        _run_file_open("open the file this_file_definitely_does_not_exist_xyz123.txt")
    )
    assert "not found" in result.lower()
    assert not result.lower().startswith("opening")


# ── run_agent() — verbatim tool result, no LLM fabrication ───────────────────

async def test_agent_file_open_returns_tool_result_verbatim():
    """
    file_open must follow the same anti-hallucination pattern as app_open:
    the tool's real result is returned as-is, with no LLM narration step
    that could paraphrase a failure into a fake success.
    """
    session = "agent-file-open-test"
    memory.clear_session(session)

    with patch("core.agent.brain") as mock_brain:
        mock_brain.generate = AsyncMock(return_value="SHOULD NOT BE USED")

        result = await run_agent(
            text="open the file this_file_definitely_does_not_exist_xyz123.txt",
            session_id=session,
            mode="professional",
            language_code="en",
        )

    # The LLM must never have been consulted for file_open — the tool's own
    # return value IS the response.
    mock_brain.generate.assert_not_called()
    assert "not found" in result.lower()
    memory.clear_session(session)
