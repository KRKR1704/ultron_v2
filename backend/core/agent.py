"""
core/agent.py — LangGraph-based intent router.

Classifies user input into one of several tool intents, executes
the appropriate tool, then generates a natural-language response
via brain.py.
"""

import logging
import re
from typing import Any

from core.brain import brain
from core.memory import memory

log = logging.getLogger(__name__)

# ── Intent keyword maps ───────────────────────────────────────────────────────

# Conversational / personal patterns that must NEVER trigger a tool.
# Checked before everything else — any match returns "direct_answer" immediately.
_CONVERSATIONAL_OVERRIDES: list[str] = [
    # ── Personal / identity ──────────────────────────────────────────────
    r"\bwhat is my\b",        # "what is my name / job / …"
    r"\bwhat'?s my\b",        # "what's my name"
    r"\bwho am i\b",
    r"\bmy name\b",           # "my name is …" / "what is my name"
    r"\bdo you remember\b",

    # ── Math / arithmetic — always answer directly ───────────────────────
    r"\d+\s*[\+\-\*\/\^]\s*\d+",   # "1+1", "10 * 5", "2^8"
    r"\bwhat is \d",                 # "what is 1+1", "what is 42"
    r"\bwhat'?s \d",                 # "what's 100 / 4"
    r"\bcalculate\b",
    r"\bsolve\b",
    r"\bcompute\b",
    r"\bhow much is \d",
    r"\btell me what is \d",         # "tell me what is 1+1"
    r"\btell me what'?s \d",

    # ── Chitchat / meta ──────────────────────────────────────────────────
    r"\bhow are you\b",
    r"\bhow do you\b",
    r"\btell me about yourself\b",
    r"\bwhat can you do\b",
    r"\bwhat do you think\b",
    r"\bare you (a|an|able|capable|ready|sure)\b",
    r"\bcan you (help|tell|show|explain|do|give)\b",
    r"\bthank(s| you)\b",
    r"\bsorry\b",
    r"\bplease\b.{0,20}\bhelp\b",

    # ── Simple factual questions Ultron should answer from knowledge ─────
    r"\bwhat (color|colour|shape|size|temperature|speed|distance) is\b",
    r"\bhow (many|much|tall|old|far|long|fast|big|small|heavy) (is|are|was|were)\b",
    r"\bwhat does .{1,40} mean\b",   # "what does CPU mean"
    r"\bdefine\b",
    r"\bexplain (what|how|why|the)\b",
]

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    # (intent_name, [keyword/phrase patterns])
    ("web_search", [
        r"\bsearch (for |the web |about )?\w",   # "search for X"
        r"\blook up\b",                           # "look up X"
        r"\blatest\b",                            # "latest news on X"
        r"\bnews (on|about|for)\b",               # "news about X" (not bare "news")
        r"\btell me about [a-zA-Z]",              # "tell me about Python" (not "tell me what is")
        r"\bwhat is the (current|latest|recent|today'?s|live)\b",  # real-time info
        r"\bwhat'?s (happening|going on|new|trending)\b",
        r"\bwho is [A-Z]",                        # "who is Elon Musk" (proper noun)
        r"\bwhere is\b",
        r"\bwhen (is|was|did|does)\b",
    ]),
    ("browser_open", [
        r"\bopen\b.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)",
        r"\bgo to\b", r"\bpull up\b", r"\bnavigate to\b",
        r"\bsearch youtube\b", r"\bsearch reddit\b", r"\bsearch google\b",
    ]),
    ("app_open", [
        r"\bopen\b.*(spotify|vscode|vs code|chrome|brave|terminal|notepad|finder|explorer|slack|discord|zoom)",
        r"\blaunch\b", r"\bstart\b.*(app|application|program)",
    ]),
    ("type_text", [
        r"\btype\b", r"\bwrite this\b", r"\benter this\b", r"\bpaste\b",
    ]),
    ("smart_home", [
        r"\bturn on\b", r"\bturn off\b", r"\blights?\b", r"\bthermostat\b",
        r"\btemperature\b", r"\bfan\b", r"\bplug\b", r"\bswitch\b",
        r"\bdim\b", r"\bbrighten\b",
    ]),
    ("calendar", [
        r"\bschedule\b", r"\bmeeting\b", r"\bcalendar\b", r"\bappointment\b",
        r"\bevent\b", r"\bbook\b.*\btime\b",
    ]),
    ("tasks", [
        r"\btask\b", r"\bremind me\b", r"\bto[- ]do\b", r"\badd to my list\b",
        r"\bcomplete\b.*\btask\b", r"\bfinish\b.*\btask\b", r"\blist.*tasks?\b",
    ]),
    ("camera_analyze", [
        r"\bwhat do you see\b", r"\blook at this\b", r"\banalyze this\b",
        r"\bwhat's in front\b", r"\bwhat am i holding\b", r"\bcamera\b",
    ]),
    ("screen_analyze", [
        r"\bwhat'?s on (the )?screen\b", r"\bexplain this\b",
        r"\bwhat am i looking at\b", r"\bread (the )?screen\b",
        r"\bscreen\b",
    ]),
]


def classify_intent(text: str) -> str:
    """
    Return the best-matching intent string for *text*.
    Falls back to "direct_answer" if no pattern matches.

    Conversational / personal phrases are checked FIRST so they never
    accidentally trigger a tool (e.g. "what is my name" must not web-search).
    """
    lower = text.lower()

    # ── Step 1: conversational guard ────────────────────────────────────────
    for pattern in _CONVERSATIONAL_OVERRIDES:
        if re.search(pattern, lower):
            return "direct_answer"

    # ── Step 2: tool intent matching ─────────────────────────────────────────
    for intent, patterns in _INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lower):
                return intent

    return "direct_answer"


# ── Tool executors ────────────────────────────────────────────────────────────

async def _run_web_search(text: str) -> str:
    from tools.web_search import search
    # Extract the core query — strip leading intent words
    query = re.sub(
        r"^(search (for|the web for|about)?|look up|find|what is|who is)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return await search(query or text)


async def _run_browser_open(text: str) -> str:
    from tools.browser_control import open_from_command
    return open_from_command(text)


async def _run_app_open(text: str) -> str:
    from tools.app_control import open_app_from_command
    return open_app_from_command(text)


async def _run_type_text(text: str) -> str:
    from tools.browser_control import type_text
    # Extract what to type — take everything after "type" / "write this"
    match = re.search(r"(?:type|write this|enter this|paste)[:\s]+(.+)", text, re.IGNORECASE)
    content = match.group(1).strip() if match else text
    return type_text(content)


async def _run_smart_home(text: str, session_id: str) -> str:
    from tools.smart_home import smart_home
    return await smart_home.execute(text)


async def _run_calendar(text: str, session_id: str) -> str:
    from tools.calendar_tasks import calendar_tasks
    return await calendar_tasks.handle_calendar(text)


async def _run_tasks(text: str, session_id: str) -> str:
    from tools.calendar_tasks import calendar_tasks
    return await calendar_tasks.handle_tasks(text)


async def _run_camera_analyze(question: str, session_id: str) -> str:
    from vision.camera import camera_capture
    from vision.ocr import extract_text
    from vision.analyzer import analyze

    frame_b64 = camera_capture.capture_frame()
    if not frame_b64:
        return "I was unable to access the camera."
    ocr_text = extract_text(frame_b64)
    return await analyze(frame_b64, question, "general", session_id, ocr_text=ocr_text)


async def _run_screen_analyze(question: str, session_id: str) -> str:
    from vision.screen import screen_capture
    from vision.ocr import extract_text
    from vision.analyzer import analyze

    screen_b64 = screen_capture.capture_screen()
    if not screen_b64:
        return "I was unable to capture the screen."

    ocr_text = extract_text(screen_b64)

    # Detect content type from OCR text
    context = _detect_screen_context(ocr_text)
    return await analyze(screen_b64, question, context, session_id, ocr_text=ocr_text)


def _detect_screen_context(ocr_text: str) -> str:
    """Heuristically guess what type of content is on screen."""
    lower = ocr_text.lower()
    code_signals = [
        "def ", "import ", "function ", "const ", "var ", "=>",
        "return ", "{", "}", "//", "/*", "class ", "public ", "private ",
    ]
    if any(sig in lower for sig in code_signals):
        return "code"

    # Very rough foreign text detection (non-ASCII ratio)
    non_ascii = sum(1 for c in ocr_text if ord(c) > 127)
    if ocr_text and non_ascii / len(ocr_text) > 0.3:
        return "foreign_text"

    doc_signals = ["dear ", "sincerely", "regards", "invoice", "total", "summary"]
    if any(sig in lower for sig in doc_signals):
        return "document"

    return "general"


# ── Public agent interface ────────────────────────────────────────────────────

async def run_agent(
    text: str,
    session_id: str,
    mode: str = "professional",
    language_code: str = "en",
    user_name: str = "sir",
) -> str:
    """
    Main entry point.

    1. Classify intent from *text*.
    2. Execute the matching tool.
    3. Pass tool result back to LLM for a natural language response.
    4. Return the final response string.
    """
    intent = classify_intent(text)
    log.info("Intent: %s for session %s", intent, session_id)

    tool_result: str | None = None

    try:
        if intent == "web_search":
            tool_result = await _run_web_search(text)

        elif intent == "browser_open":
            tool_result = await _run_browser_open(text)

        elif intent == "app_open":
            tool_result = await _run_app_open(text)

        elif intent == "type_text":
            tool_result = await _run_type_text(text)

        elif intent == "smart_home":
            tool_result = await _run_smart_home(text, session_id)

        elif intent == "calendar":
            tool_result = await _run_calendar(text, session_id)

        elif intent == "tasks":
            tool_result = await _run_tasks(text, session_id)

        elif intent == "camera_analyze":
            tool_result = await _run_camera_analyze(text, session_id)

        elif intent == "screen_analyze":
            tool_result = await _run_screen_analyze(text, session_id)

        # direct_answer falls through — tool_result stays None

    except Exception as err:
        log.error("Tool execution failed for intent %s: %s", intent, err)
        tool_result = f"Tool encountered an issue: {err}"

    # Build the prompt for the LLM
    if tool_result is not None:
        augmented_prompt = (
            f"User request: {text}\n\n"
            f"Tool result: {tool_result}\n\n"
            "Based on the tool result above, provide a concise natural language "
            "response to the user's request. Do not repeat the raw tool data verbatim."
        )
    else:
        augmented_prompt = text

    return await brain.generate(
        prompt=augmented_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    )
