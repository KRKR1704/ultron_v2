"""
test_02_config.py — Tests for config loading/saving (load_config, save_config, _DEFAULT_CONFIG).
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from main import load_config, save_config, _DEFAULT_CONFIG


_REQUIRED_KEYS = {
    "mode",
    "language",
    "language_name",
    "camera_active",
    "screen_active",
    "wake_word_active",
    "user_name",
    "session_timeout_minutes",
}


def test_default_config_has_required_keys():
    """_DEFAULT_CONFIG must contain all expected configuration keys."""
    for key in _REQUIRED_KEYS:
        assert key in _DEFAULT_CONFIG, f"Missing required key in _DEFAULT_CONFIG: {key!r}"


def test_load_config_returns_dict():
    """load_config() must always return a dict."""
    cfg = load_config()
    assert isinstance(cfg, dict)


def test_save_and_reload_config():
    """save_config followed by load_config must round-trip correctly."""
    test_config = {
        **_DEFAULT_CONFIG,
        "mode": "casual",
        "language": "hi",
        "user_name": "boss",
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        tmp_path = Path(tmp.name)

    try:
        # Patch the config path to our temp file
        with patch("main._CONFIG_PATH", tmp_path):
            save_config(test_config)
            reloaded = load_config()

        assert reloaded["mode"] == "casual"
        assert reloaded["language"] == "hi"
        assert reloaded["user_name"] == "boss"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_config_merges_with_defaults():
    """
    A partial config file (only some keys) must be merged with _DEFAULT_CONFIG
    so that all required keys are present in the returned dict.
    """
    partial = {"mode": "casual"}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as tmp:
        json.dump(partial, tmp)
        tmp_path = Path(tmp.name)

    try:
        with patch("main._CONFIG_PATH", tmp_path):
            cfg = load_config()

        # All default keys must be present
        for key in _REQUIRED_KEYS:
            assert key in cfg, f"Merged config is missing key: {key!r}"

        # The user-supplied value must win
        assert cfg["mode"] == "casual"
    finally:
        tmp_path.unlink(missing_ok=True)


def test_invalid_config_file_returns_defaults():
    """
    When the config file does not exist or is corrupt, load_config() must
    return the default config without raising an exception.
    """
    nonexistent = Path("/tmp/__ultron_nonexistent_config_xyz.json")
    nonexistent.unlink(missing_ok=True)

    with patch("main._CONFIG_PATH", nonexistent):
        cfg = load_config()

    assert isinstance(cfg, dict)
    for key in _REQUIRED_KEYS:
        assert key in cfg, f"Default config missing key: {key!r}"
    assert cfg["mode"] == _DEFAULT_CONFIG["mode"]
