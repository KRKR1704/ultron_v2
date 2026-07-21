"""
helpers.py — Shared service-detection utilities and pytest skip marks.

Imported by conftest.py AND by individual test modules that need to apply
skip marks at module level (e.g. @skip_no_piper on a test function).

This is a plain Python module — NOT a conftest — so it can be imported
with a regular `from tests.helpers import ...` or (when tests/ is on
sys.path) `from helpers import ...`.
"""

import os
import subprocess

import pytest


# ── Service detection ──────────────────────────────────────────────────────────

def ollama_available() -> bool:
    """Return True if Ollama is reachable on the configured URL."""
    import httpx

    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def elevenlabs_available() -> bool:
    """Return True if ELEVENLABS_API_KEY is set in the environment."""
    return bool(os.getenv("ELEVENLABS_API_KEY", "").strip())


def home_assistant_available() -> bool:
    """Return True if HASS_TOKEN is set and the HASS_URL is reachable."""
    if not os.getenv("HASS_TOKEN", "").strip():
        return False
    url = os.getenv("HASS_URL", "http://homeassistant.local:8123")
    try:
        import httpx
        resp = httpx.get(f"{url}/api/", timeout=3.0)
        return resp.status_code in (200, 401)  # 401 = reachable but needs auth
    except Exception:
        return False


def piper_available() -> bool:
    """Return True if the `piper` executable is on PATH."""
    try:
        result = subprocess.run(
            ["piper", "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ── Pytest skip marks (evaluated once at import time) ─────────────────────────

skip_no_ollama = pytest.mark.skipif(
    not ollama_available(),
    reason="Ollama is not running (set OLLAMA_BASE_URL or start ollama serve)",
)

skip_no_elevenlabs = pytest.mark.skipif(
    not elevenlabs_available(),
    reason="ELEVENLABS_API_KEY is not set",
)

skip_no_home_assistant = pytest.mark.skipif(
    not home_assistant_available(),
    reason="Home Assistant is not reachable (set HASS_URL + HASS_TOKEN)",
)

skip_no_piper = pytest.mark.skipif(
    not piper_available(),
    reason="piper executable not found on PATH",
)
