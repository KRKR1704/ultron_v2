"""
tools/datetime_tool.py — Real date/time facts, computed locally, never guessed.

Same anti-hallucination pattern as tools/calculator.py: the LLM must never
guess the current date/time (it has no way to know it — its knowledge has a
training cutoff and no live clock) or compute a day-difference itself.
Python's datetime.now() (the local system clock — zero API calls, zero
latency, works fully offline) is the single source of truth for "now";
dateparser (already a project dependency — see tools/calendar_tasks.py's
_parse_time()) resolves relative phrases like "next Friday" for
day-difference calculations.

Examples:
    >>> get_current_datetime_fact()  # doctest: +SKIP
    ('Thursday, August 06, 2026, 02:35 PM', ['2026', '6'])

    >>> extract_days_until_target("how many days until Friday")
    'Friday'
    >>> extract_days_until_target("what time is it")

    >>> days_until("Friday")  # doctest: +SKIP
    {"success": True, "days": 3, "target_date": "Friday, August 09, 2026", "error": None}
"""

import re
from datetime import datetime
from typing import Optional

import dateparser

# ── Current date/time ────────────────────────────────────────────────────────


def get_current_datetime_fact(now: Optional[datetime] = None) -> tuple[str, list[str]]:
    """
    Return (fact, anchors):
      - fact: a natural, unambiguous string, e.g.
        "Thursday, August 06, 2026, 02:35 PM" — for the LLM to narrate.
      - anchors: digit-only substrings (year, day-of-month) that MUST appear
        in the LLM's narrated response for it to count as grounded. Digits
        are language-neutral (unlike day/month NAMES, which are English
        words here) — this matters because the system prompt forces the
        response into whatever language was detected, so requiring the
        literal English word "Thursday" to survive inside e.g. a Spanish
        response would be an unreasonable ask, but "2026" and "6" will
        naturally appear in a Spanish date phrase too ("jueves, 6 de agosto
        de 2026"). This is a deliberate, disclosed deviation from
        calculator.py's single-exact-string check, justified by that
        language-neutrality difference.
    """
    now = now or datetime.now()
    fact = now.strftime("%A, %B %d, %Y, %I:%M %p")
    anchors = [str(now.year), str(now.day)]
    return fact, anchors


# ── "How many days until X" ───────────────────────────────────────────────────

_DAYS_UNTIL_PATTERNS = [
    re.compile(r"\bhow many days?\s+(?:until|till|to|before)\s+(.+?)[\?\.!]*$", re.IGNORECASE),
    re.compile(r"\bdays?\s+(?:until|till|before)\s+(.+?)[\?\.!]*$", re.IGNORECASE),
]


def extract_days_until_target(text: str) -> Optional[str]:
    """
    Pull the target date phrase out of a "how many days until X" style
    request, e.g. "how many days until Friday" -> "Friday". Returns None if
    *text* isn't that shape of request — the caller then treats it as a
    plain "what's the date/time now" request instead.
    """
    if not text:
        return None
    for pattern in _DAYS_UNTIL_PATTERNS:
        match = pattern.search(text)
        if match:
            target = match.group(1).strip()
            if target:
                return target
    return None


def days_until(target_text: str, now: Optional[datetime] = None) -> dict:
    """
    Compute the number of CALENDAR days from *now* until the date described
    by *target_text* (e.g. "Friday", "next Monday", "December 25"), via
    dateparser — never guessed by an LLM.

    Returns:
        {"success": bool, "days": int | None, "target_date": str | None,
         "error": str | None}
    """
    now = now or datetime.now()
    if not target_text or not target_text.strip():
        return {"success": False, "days": None, "target_date": None, "error": "No target date given."}

    try:
        parsed = dateparser.parse(
            target_text,
            settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now},
        )
    except Exception as err:
        return {"success": False, "days": None, "target_date": None, "error": str(err)}

    if parsed is None:
        return {
            "success": False, "days": None, "target_date": None,
            "error": f"I couldn't understand the date '{target_text}'.",
        }

    delta_days = (parsed.date() - now.date()).days
    return {
        "success": True,
        "days": delta_days,
        "target_date": parsed.strftime("%A, %B %d, %Y"),
        # Anchors for the grounding safeguard — digits from the TARGET date,
        # not the days-count. The days-count anchor alone would break the
        # "guaranteed correct" fallback template for days==0/1, whose
        # natural phrasing ("today, ..."/"tomorrow, ...") never states the
        # digit "0"/"1" at all — target-date digits are always embedded in
        # every phrasing branch (today/tomorrow/N days from now/N days ago),
        # so they're the safe choice, mirroring get_current_datetime_fact()'s
        # own anchor design.
        "anchors": [str(parsed.year), str(parsed.day)],
        "error": None,
    }
