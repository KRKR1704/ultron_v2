"""
tools/app_control.py — Launch desktop applications and open files.
"""

import logging
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

_SYSTEM = platform.system()  # "Windows", "Darwin", "Linux"

# ── App name → executable mapping ────────────────────────────────────────────
# Each entry is (windows_cmd, mac_cmd, linux_cmd)
# None means not available on that platform.

APP_MAP: dict[str, tuple[Optional[str], Optional[str], Optional[str]]] = {
    "vscode":    ("code",                 "code",              "code"),
    "vs code":   ("code",                 "code",              "code"),
    "visual studio code": ("code",        "code",              "code"),
    "spotify":   ("spotify",              "open -a Spotify",   "spotify"),
    "chrome":    ("chrome",               "open -a 'Google Chrome'", "google-chrome"),
    "brave":     ("brave",                "open -a 'Brave Browser'", "brave-browser"),
    "firefox":   ("firefox",              "open -a Firefox",   "firefox"),
    "terminal":  ("cmd.exe",              "open -a Terminal",  "x-terminal-emulator"),
    "cmd":       ("cmd.exe",              None,                None),
    "powershell":("powershell.exe",       None,                None),
    "notepad":   ("notepad.exe",          None,                None),
    "explorer":  ("explorer.exe",         None,                None),
    "finder":    (None,                   "open -a Finder",    None),
    "slack":     ("slack",                "open -a Slack",     "slack"),
    "discord":   ("discord",              "open -a Discord",   "discord"),
    "zoom":      ("zoom",                 "open -a Zoom",      "zoom"),
    "teams":     ("teams",                "open -a 'Microsoft Teams'", "teams"),
    "word":      ("winword.exe",          "open -a 'Microsoft Word'", "soffice"),
    "excel":     ("excel.exe",            "open -a 'Microsoft Excel'", "soffice"),
    "powerpoint":("powerpnt.exe",         "open -a 'Microsoft PowerPoint'", "soffice"),
    "notion":    ("notion",               "open -a Notion",    "notion"),
    "obsidian":  ("obsidian",             "open -a Obsidian",  "obsidian"),
    "vlc":       ("vlc",                  "open -a VLC",       "vlc"),
    "steam":     ("steam",                "open -a Steam",     "steam"),
    "calculator":("calc.exe",             "open -a Calculator","gnome-calculator"),
    "paint":     ("mspaint.exe",          None,                "gimp"),
    "photoshop": ("photoshop.exe",        "open -a Photoshop", None),
}


def _resolve_command(app_key: str) -> Optional[str]:
    """Return the platform-specific command string for an app key."""
    entry = APP_MAP.get(app_key.lower())
    if not entry:
        return None
    win_cmd, mac_cmd, linux_cmd = entry
    if _SYSTEM == "Windows":
        return win_cmd
    elif _SYSTEM == "Darwin":
        return mac_cmd
    else:
        return linux_cmd


def open_app(app_name: str) -> str:
    """
    Launch an application by name.
    Returns a confirmation or error string.
    """
    key = app_name.lower().strip()
    cmd = _resolve_command(key)

    if cmd is None:
        # Try a generic subprocess launch using the raw name
        cmd = key

    try:
        if _SYSTEM == "Windows":
            subprocess.Popen(cmd, shell=True)
        elif _SYSTEM == "Darwin":
            # Mac open commands need shell=True when using "open -a ..."
            subprocess.Popen(cmd, shell=True)
        else:
            subprocess.Popen(cmd.split(), shell=False)

        log.info("Launched app: %s", cmd)
        return f"Launching {app_name}."

    except Exception as err:
        log.error("Failed to launch %s: %s", app_name, err)
        return f"Could not launch {app_name}: {err}"


def open_file(path: str) -> str:
    """
    Open a file with its default application.
    Uses os.startfile on Windows, 'open' on Mac, 'xdg-open' on Linux.
    """
    file_path = Path(path).expanduser()
    if not file_path.exists():
        return f"File not found: {path}"

    try:
        if _SYSTEM == "Windows":
            os.startfile(str(file_path))
        elif _SYSTEM == "Darwin":
            subprocess.Popen(["open", str(file_path)])
        else:
            subprocess.Popen(["xdg-open", str(file_path)])

        return f"Opening {file_path.name}."

    except Exception as err:
        log.error("Failed to open file %s: %s", path, err)
        return f"Could not open file: {err}"


def open_app_from_command(command: str) -> str:
    """
    Parse a natural language command and launch the appropriate app.
    E.g. "open VS Code", "launch Spotify", "start terminal".
    """
    lower = command.lower()

    # Try each known app name in order from longest to shortest (greedy match)
    sorted_keys = sorted(APP_MAP.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if key in lower:
            return open_app(key)

    # Extract app name after trigger verb
    match = re.search(
        r"(?:open|launch|start|run)\s+(.+?)(?:\s+(?:app|application|program))?$",
        lower,
    )
    if match:
        return open_app(match.group(1).strip())

    return f"I couldn't identify an application to open from: '{command}'"
