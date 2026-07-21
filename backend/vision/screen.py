"""
vision/screen.py — Screen capture (passive monitoring + on-demand).

Passive mode polls every 5 seconds using mss.
Screenshots are NEVER written to disk.
Proactive suggestions are queued when the user stays on the same window > 10 min.
"""

import base64
import io
import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

_PASSIVE_INTERVAL = 5.0           # seconds between passive captures
_IDLE_THRESHOLD = 10 * 60         # 10 minutes → proactive suggestion


class ScreenCapture:
    """Manages passive screen monitoring and on-demand screenshot capture."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._active = False

        # Latest window state
        self._current_app: str = ""
        self._current_title: str = ""
        self._window_since: float = 0.0

        # Queue proactive suggestions for the WS handler to pick up
        self.suggestion_queue: list[str] = []
        self._queue_lock = threading.Lock()

    # ── Public control ────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._active = True
        self._thread = threading.Thread(
            target=self._run_passive,
            name="screen-monitor",
            daemon=True,
        )
        self._thread.start()
        log.info("Screen passive monitor started.")

    def stop(self) -> None:
        self._stop_event.set()
        self._active = False
        if self._thread:
            self._thread.join(timeout=5.0)
        log.info("Screen passive monitor stopped.")

    @property
    def is_active(self) -> bool:
        return self._active and (self._thread is not None and self._thread.is_alive())

    def get_state(self) -> dict:
        return {
            "app_name": self._current_app,
            "window_title": self._current_title,
            "timestamp": self._window_since,
        }

    def pop_suggestion(self) -> Optional[str]:
        """Return and remove the next proactive suggestion, or None."""
        with self._queue_lock:
            if self.suggestion_queue:
                return self.suggestion_queue.pop(0)
        return None

    # ── On-demand capture ─────────────────────────────────────────────────────

    def capture_screen(self) -> str:
        """
        Capture the full screen via mss.
        Returns base64-encoded JPEG string.  NEVER writes to disk.
        """
        try:
            import mss
            from PIL import Image

            with mss.mss() as sct:
                monitor = sct.monitors[0]  # entire virtual screen
                shot = sct.grab(monitor)

            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return base64.b64encode(buf.getvalue()).decode("utf-8")

        except ImportError:
            log.error("mss or Pillow not installed — cannot capture screen.")
            return ""
        except Exception as err:
            log.error("Screen capture failed: %s", err)
            return ""

    # ── Background thread ─────────────────────────────────────────────────────

    def _run_passive(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as err:
                log.debug("Passive screen tick error: %s", err)
            self._stop_event.wait(timeout=_PASSIVE_INTERVAL)

    def _tick(self) -> None:
        """Check the active window and push a proactive suggestion if idle too long."""
        app, title = self._get_active_window()

        if app != self._current_app or title != self._current_title:
            # Window changed — reset timer
            self._current_app = app
            self._current_title = title
            self._window_since = time.time()
        else:
            idle_seconds = time.time() - self._window_since
            if idle_seconds >= _IDLE_THRESHOLD:
                suggestion = self._build_suggestion(app, title)
                with self._queue_lock:
                    self.suggestion_queue.append(suggestion)
                # Reset so we don't spam every 5s
                self._window_since = time.time()

    @staticmethod
    def _get_active_window() -> tuple[str, str]:
        """Return (process_name, window_title) of the currently focused window."""
        try:
            import psutil
            try:
                import pygetwindow as gw
                wins = gw.getActiveWindow()
                title = wins.title if wins else ""
            except Exception:
                title = ""

            # Get the focused process name via psutil
            try:
                import subprocess
                import platform

                if platform.system() == "Windows":
                    result = subprocess.run(
                        ["powershell", "-Command",
                         "Get-Process | Where-Object {$_.MainWindowHandle -ne 0} | "
                         "Sort-Object CPU -Descending | Select-Object -First 1 -ExpandProperty Name"],
                        capture_output=True, text=True, timeout=2
                    )
                    app_name = result.stdout.strip()
                else:
                    app_name = ""
            except Exception:
                app_name = ""

            return app_name, title

        except Exception:
            return "", ""

    @staticmethod
    def _build_suggestion(app: str, title: str) -> str:
        suggestions = {
            "code": f"I noticed you've been in '{title}' for a while. Need help with your code?",
            "chrome": f"You've been browsing for a while. Can I look something up for you?",
            "brave": f"You've been browsing for a while. Can I look something up for you?",
            "excel": f"Working on a spreadsheet? I can help with formulas or analysis.",
            "word": f"I see you're working on a document. Need help with writing?",
        }
        app_lower = app.lower()
        for key, msg in suggestions.items():
            if key in app_lower:
                return msg
        return f"You've been on '{title or app}' for a while. Need any assistance?"


# ── Module-level singleton ────────────────────────────────────────────────────
screen_capture = ScreenCapture()
