"""
conftest.py — Shared pytest fixtures and helpers for the ULTRON backend test suite.

Adds backend/ to sys.path so all backend modules are importable directly.
Does NOT trigger the FastAPI lifespan — the app is used as a plain ASGI object.
"""

import base64
import struct
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

# ── Path setup ─────────────────────────────────────────────────────────────────
# Ensures `from core.memory import memory` etc. all work from within the tests/
# directory without installing the backend as a package.
# Also adds tests/ itself so `from helpers import ...` works in test modules.

_TESTS_DIR = Path(__file__).parent
_BACKEND_DIR = _TESTS_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))
sys.path.insert(0, str(_TESTS_DIR))

# ── Import app AFTER path is set up ───────────────────────────────────────────
from main import app, app_state, load_config  # noqa: E402

# ── Re-export service helpers from helpers.py so existing imports still work ──
from helpers import (  # noqa: F401  (re-exported for backward compat)
    ollama_available,
    elevenlabs_available,
    home_assistant_available,
    piper_available,
    skip_no_ollama,
    skip_no_elevenlabs,
    skip_no_home_assistant,
    skip_no_piper,
)


# ── Vault test isolation ─────────────────────────────────────────────────────
# Autouse + session-scoped: repoints the module-level `vault` singleton
# (core/vault.py) at a tmp_path_factory directory for the ENTIRE test run, so
# the 200+ existing tests that already exercise run_agent()/`/chat`/`/voice`
# never write into the real backend/vault/ (which holds real personal
# conversation data) and never slow down. Tests specifically exercising the
# vault construct their own isolated `Vault(root=tmp_path)` instances instead.

@pytest.fixture(autouse=True, scope="session")
def _isolated_vault(tmp_path_factory):
    from core.vault import vault

    test_root = tmp_path_factory.mktemp("vault_root")
    vault.root = test_root
    vault.raw_dir = test_root / "raw"
    vault.wiki_dir = test_root / "wiki"
    vault.outputs_dir = test_root / "outputs"
    yield vault


# ── Core fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def client():
    """
    A synchronous Starlette TestClient wrapping the FastAPI app.

    Uses the `with` context manager so ASGI lifespan events fire cleanly
    (startup/shutdown) — but since we haven't wired external services in tests,
    failures there are suppressed in the app itself.
    """
    # Ensure app_state has a minimal config so routes don't KeyError
    if not app_state.get("config"):
        app_state["config"] = load_config()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(scope="session")
async def async_client():
    """An async HTTPX client for testing async endpoints."""
    if not app_state.get("config"):
        app_state["config"] = load_config()

    async with httpx.AsyncClient(
        app=app, base_url="http://testserver", timeout=30.0
    ) as ac:
        yield ac


@pytest.fixture
def session_id() -> str:
    """Fixed session ID for tests that need a stable session."""
    return "test-session-001"


@pytest.fixture
def test_audio_base64() -> str:
    """
    Minimal valid 44-byte WAV header for silence (no PCM data).
    Encodes: RIFF header + WAVE + fmt chunk + data chunk (empty).
    """
    # Build a minimal WAV header with 0 bytes of audio data
    sample_rate = 16000
    channels = 1
    sample_width = 2  # 16-bit
    data_size = 0
    byte_rate = sample_rate * channels * sample_width
    block_align = channels * sample_width

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,   # file size - 8
        b"WAVE",
        b"fmt ",
        16,               # fmt chunk size
        1,                # PCM format
        channels,
        sample_rate,
        byte_rate,
        block_align,
        sample_width * 8, # bits per sample
        b"data",
        data_size,
    )
    return base64.b64encode(header).decode("utf-8")


@pytest.fixture
def test_image_base64() -> str:
    """
    Minimal valid 1x1 white pixel PNG encoded as base64.
    Constructed from the standard PNG byte signature + IHDR + IDAT + IEND.
    """
    # Minimal 1x1 white PNG (67 bytes)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n"               # PNG signature
        b"\x00\x00\x00\rIHDR"              # IHDR length + type
        b"\x00\x00\x00\x01"               # width = 1
        b"\x00\x00\x00\x01"               # height = 1
        b"\x08\x02"                        # 8-bit depth, RGB
        b"\x00\x00\x00"                    # compression, filter, interlace
        b"\x90wS\xde"                      # CRC
        b"\x00\x00\x00\x0cIDAT"           # IDAT length + type
        b"x\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"  # zlib data
        b"\x00\x00\x00\x00IEND"            # IEND length + type
        b"\xaeB`\x82"                      # CRC
    )
    return base64.b64encode(png_bytes).decode("utf-8")


@pytest.fixture
def reset_mode(client):
    """
    After the test completes, reset the app mode to 'professional'.
    Not autouse — opt in per-test with `def test_foo(reset_mode)`.
    """
    yield
    # Restore professional mode after the test
    app_state["config"]["mode"] = "professional"
