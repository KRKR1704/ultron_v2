"""
test_03_memory.py — Tests for core/memory.py ConversationMemory.
"""

import threading
import time

import pytest

from core.memory import ConversationMemory


@pytest.fixture
def mem():
    """Fresh ConversationMemory instance for each test."""
    return ConversationMemory(session_timeout_minutes=30)


def test_add_and_get_message(mem):
    """Messages added via add_message must appear in get_history."""
    mem.add_message("session-1", "user", "Hello!")
    mem.add_message("session-1", "assistant", "Hello to you too, sir.")

    history = mem.get_history("session-1")

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello!"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hello to you too, sir."


def test_get_history_empty_session_returns_empty_list(mem):
    """get_history for an unknown session must return an empty list, not raise."""
    history = mem.get_history("nonexistent-session")
    assert history == []


def test_clear_session_removes_messages(mem):
    """clear_session must delete all messages for that session only."""
    mem.add_message("session-a", "user", "test message")
    mem.add_message("session-b", "user", "another message")

    mem.clear_session("session-a")

    assert mem.get_history("session-a") == []
    # session-b must be unaffected
    assert len(mem.get_history("session-b")) == 1


def test_clear_all_removes_all_sessions(mem):
    """clear_all must wipe every session in memory."""
    for i in range(5):
        mem.add_message(f"session-{i}", "user", f"message {i}")

    mem.clear_all()

    for i in range(5):
        assert mem.get_history(f"session-{i}") == []


def test_message_trimming_keeps_last_20_messages(mem):
    """
    The memory store keeps only the last _MAX_PAIRS*2 = 20 messages per session.
    Adding 25 messages must result in exactly 20 stored.
    """
    sid = "trim-test"
    for i in range(25):
        mem.add_message(sid, "user", f"user message {i}")

    history = mem.get_history(sid)
    assert len(history) == 20
    # The most recent messages must be at the end
    assert history[-1]["content"] == "user message 24"


def test_session_expiry(mem):
    """
    Sessions idle longer than the timeout must be purged on the next
    get_history call (via _purge_expired).
    """
    # Create a memory with 1-second timeout
    short_mem = ConversationMemory(session_timeout_minutes=0)
    short_mem._timeout = 1  # 1 second

    short_mem.add_message("expiry-session", "user", "I will expire soon")

    # Wait for the session to expire
    time.sleep(1.1)

    # get_history triggers _purge_expired internally
    history = short_mem.get_history("expiry-session")
    assert history == []


def test_multiple_sessions_independent(mem):
    """Messages in one session must not appear in another session."""
    mem.add_message("session-alpha", "user", "alpha message")
    mem.add_message("session-beta", "user", "beta message")

    alpha = mem.get_history("session-alpha")
    beta = mem.get_history("session-beta")

    assert len(alpha) == 1
    assert alpha[0]["content"] == "alpha message"
    assert len(beta) == 1
    assert beta[0]["content"] == "beta message"


def test_thread_safety(mem):
    """
    10 threads adding messages concurrently must not raise any exceptions
    and all messages must be recorded (order is non-deterministic).
    """
    errors: list[Exception] = []

    def add_messages(thread_id: int):
        try:
            for i in range(5):
                mem.add_message(
                    "shared-session",
                    "user",
                    f"thread-{thread_id}-msg-{i}",
                )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=add_messages, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Exceptions raised in threads: {errors}"

    history = mem.get_history("shared-session")
    # 10 threads × 5 messages = 50 total, but trimming keeps only last 20
    assert len(history) == 20
