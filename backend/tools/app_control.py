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


# ── Common folder name → real OS path mapping ────────────────────────────────
# Mirrors the APP_MAP pattern above: a small, explicit lookup rather than
# guessing paths. Covers the folders users actually ask for by name.

_COMMON_FOLDERS: dict[str, Path] = {
    "downloads": Path.home() / "Downloads",
    "desktop":   Path.home() / "Desktop",
    "documents": Path.home() / "Documents",
    "home":      Path.home(),
}

# Alias word (any supported language) → canonical _COMMON_FOLDERS key.
# Longest-first matching is done by the caller so e.g. "my documents"
# resolves before a shorter, coincidental substring match could.
_FOLDER_NAME_ALIASES: dict[str, str] = {
    # English
    "my downloads folder": "downloads", "my downloads": "downloads", "downloads folder": "downloads", "downloads": "downloads",
    "my desktop folder": "desktop", "my desktop": "desktop", "desktop folder": "desktop", "desktop": "desktop",
    "my documents folder": "documents", "my documents": "documents", "documents folder": "documents", "documents": "documents",
    "my project folder": "home", "my home folder": "home",
    # Spanish
    "mis descargas": "downloads", "descargas": "downloads",
    "mi escritorio": "desktop", "escritorio": "desktop",
    "mis documentos": "documents", "documentos": "documents",
    # French
    "mes téléchargements": "downloads", "téléchargements": "downloads", "telechargements": "downloads",
    "mon bureau": "desktop", "bureau": "desktop",
    "mes documents": "documents",
    # Hindi
    "डाउनलोड फ़ोल्डर": "downloads", "डाउनलोड": "downloads",
    "डेस्कटॉप": "desktop",
    "दस्तावेज़ फ़ोल्डर": "documents", "दस्तावेज़": "documents",
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


def open_file_from_command(command: str) -> str:
    """
    Parse a natural language file/folder-opening command and open it via
    open_file(). Handles:
      - Common folder references ("my downloads folder", "open my desktop"),
        including a handful of non-English folder-name synonyms.
      - Absolute paths (Windows drive-letter or POSIX root).
      - A bare filename/relative path following a trigger verb.

    Never fabricates success — the return value is always open_file()'s own
    real result (or a graceful "couldn't identify" string if no path could
    be extracted at all), same anti-hallucination pattern as open_app().
    """
    lower = command.lower()

    # Common folder references — longest alias first so e.g. "my documents"
    # isn't shadowed by a shorter, unrelated substring match.
    for alias in sorted(_FOLDER_NAME_ALIASES.keys(), key=len, reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            folder_key = _FOLDER_NAME_ALIASES[alias]
            return open_file(str(_COMMON_FOLDERS[folder_key]))

    # Absolute path: Windows drive letter or POSIX root.
    path_match = re.search(r"[a-zA-Z]:[\\/][^\s\"']+|/[^\s\"']+", command)
    if path_match:
        return open_file(path_match.group(0))

    # Bare filename/relative path after a trigger verb ("open notes.txt",
    # "show me the file report.pdf").
    match = re.search(
        r"(?:open|show(?:\s+me)?|launch)\s+(?:the\s+)?(?:file|folder|directory)?\s*(.+)",
        lower,
    )
    if match:
        candidate = match.group(1).strip().strip(".,!?\"'")
        if candidate:
            return open_file(candidate)

    return f"I couldn't identify a file or folder to open from: '{command}'"


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
