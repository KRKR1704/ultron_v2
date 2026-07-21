"""
tools/browser_control.py — Browser URL routing, search, and text typing.
"""

import logging
import os
import re
import urllib.parse
import webbrowser
from typing import Optional

import pyautogui
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)

_BRAVE_PATH = os.getenv("BRAVE_PATH", "")

# ── Known site shortcuts ──────────────────────────────────────────────────────

_SITE_MAP: dict[str, str] = {
    "github":     "https://github.com",
    "youtube":    "https://www.youtube.com",
    "reddit":     "https://www.reddit.com",
    "twitter":    "https://twitter.com",
    "x":          "https://x.com",
    "google":     "https://www.google.com",
    "gmail":      "https://mail.google.com",
    "drive":      "https://drive.google.com",
    "docs":       "https://docs.google.com",
    "sheets":     "https://sheets.google.com",
    "notion":     "https://www.notion.so",
    "slack":      "https://slack.com",
    "discord":    "https://discord.com",
    "netflix":    "https://www.netflix.com",
    "spotify":    "https://open.spotify.com",
    "amazon":     "https://www.amazon.com",
    "stackoverflow": "https://stackoverflow.com",
    "wikipedia":  "https://www.wikipedia.org",
    "linkedin":   "https://www.linkedin.com",
    "instagram":  "https://www.instagram.com",
    "facebook":   "https://www.facebook.com",
}

# ── Search URL templates ──────────────────────────────────────────────────────

_SEARCH_URLS: dict[str, str] = {
    "youtube":  "https://www.youtube.com/results?search_query={}",
    "reddit":   "https://www.reddit.com/search/?q={}",
    "google":   "https://www.google.com/search?q={}",
    "github":   "https://github.com/search?q={}",
    "brave":    "https://search.brave.com/search?q={}",
}


# ── Public functions ──────────────────────────────────────────────────────────

def open_url(url: str) -> str:
    """Open *url* in the default browser (or Brave if configured)."""
    try:
        if _BRAVE_PATH and os.path.exists(_BRAVE_PATH):
            import subprocess
            subprocess.Popen([_BRAVE_PATH, url])
        else:
            webbrowser.open(url)
        log.info("Opened URL: %s", url)
        return f"Opening {url}"
    except Exception as err:
        log.error("Failed to open URL: %s", err)
        return f"Could not open URL: {err}"


def search(query: str, platform: str = "brave") -> str:
    """Construct the correct search URL for *platform* and open it."""
    encoded = urllib.parse.quote_plus(query)
    template = _SEARCH_URLS.get(platform.lower(), _SEARCH_URLS["brave"])
    url = template.format(encoded)
    return open_url(url)


def type_text(text: str) -> str:
    """Type *text* at the current cursor position using pyautogui."""
    try:
        pyautogui.write(text, interval=0.05)
        return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"
    except Exception as err:
        log.error("pyautogui type error: %s", err)
        return f"Could not type text: {err}"


def open_from_command(command: str) -> str:
    """
    Parse a natural language browser command and open the appropriate URL.
    Handles both site lookups and platform-specific searches.
    """
    lower = command.lower()

    # Platform-specific search: "search youtube for cats"
    for platform in _SEARCH_URLS:
        match = re.search(
            rf"search\s+{platform}\s+for\s+(.+)", lower
        )
        if match:
            return search(match.group(1).strip(), platform)

    # Generic search: "search for python tutorials"
    match = re.search(r"search\s+(?:for\s+)?(.+)", lower)
    if match:
        query = match.group(1).strip()
        # Check if it's a known site name
        for site, url in _SITE_MAP.items():
            if site in query:
                return open_url(url)
        return search(query)

    # Direct site open: "open github", "go to spotify", "pull up reddit"
    for site, url in _SITE_MAP.items():
        if site in lower:
            return open_url(url)

    # URL-like string in the command
    url_match = re.search(r"https?://\S+", command)
    if url_match:
        return open_url(url_match.group(0))

    domain_match = re.search(r"(\w+\.\w{2,})", lower)
    if domain_match:
        return open_url(f"https://{domain_match.group(1)}")

    return f"I couldn't determine a URL from: '{command}'"
