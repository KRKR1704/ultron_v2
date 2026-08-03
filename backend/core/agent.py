"""
core/agent.py — Regex-based intent router.

Classifies user input into one of several tool intents using plain
`re` pattern matching (NOT LangGraph — `langgraph` is a listed
dependency but is not imported or used anywhere in this module or
elsewhere in the backend). Once an intent is classified, the matching
tool is executed and, for most intents, the tool's result is handed to
brain.py to phrase a natural-language response. `app_open` is the
exception: its tool result is returned to the user verbatim (see
`run_agent()`) so a launch failure can never be narrated as a success.
"""

import logging
import re
from typing import Any, Optional

from core.brain import brain
from core.memory import memory
from tools.app_control import APP_MAP

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

    # NOTE: arithmetic ("what is 1+1", "calculate", "solve", etc.) used to be
    # forced to direct_answer here — meaning math questions went straight to
    # the LLM to "answer" from scratch, which is exactly how small local
    # models hallucinate numbers (the same question could get 3 different
    # wrong answers). Real arithmetic is now its own "calculate" intent
    # (see classify_intent() below) backed by tools/calculator.py's safe,
    # whitelisted evaluator — the LLM only narrates the real computed
    # result, it never computes anything itself.

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

# Built from tools.app_control.APP_MAP so the intent classifier and the
# actual app map can never drift apart — any app added to APP_MAP becomes
# detectable here automatically, with zero additional code changes.
# Longest names first so e.g. "visual studio code" matches before "code"-less
# alternatives could shadow it.
_APP_NAMES_PATTERN = "|".join(
    re.escape(name) for name in sorted(APP_MAP.keys(), key=len, reverse=True)
)

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
        rf"\bopen\b.*\b({_APP_NAMES_PATTERN})\b",
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

    "calculate" is checked FIRST, ahead of even the conversational guard:
    extract_math_expression() is strict enough (requires actual digits +
    an operator/function, and excludes phone-number/date-shaped text) that
    it never spuriously fires on personal/chitchat text like "what is my
    name" (no digits) or "how much is 5 years in days" (no operator) — so
    checking it first is safe and is what lets genuine arithmetic like
    "how much is 100*5" reach the calculator instead of being swallowed by
    the "how much (is|are)" conversational override below.

    After that, conversational / personal phrases are checked so they never
    accidentally trigger a different tool (e.g. "what is my name" must not
    web-search).
    """
    lower = text.lower()

    # ── Step 1: calculate — real arithmetic, never left to the LLM ──────────
    from tools.calculator import extract_math_expression
    if extract_math_expression(text) is not None:
        return "calculate"

    # ── Step 2: conversational guard ────────────────────────────────────────
    for pattern in _CONVERSATIONAL_OVERRIDES:
        if re.search(pattern, lower):
            return "direct_answer"

    # ── Step 3: tool intent matching ─────────────────────────────────────────
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


async def _run_camera_analyze(question: str, session_id: str, language_code: str = "en") -> str:
    from vision.camera import camera_capture
    from vision.ocr import extract_text
    from vision.analyzer import analyze

    frame_b64 = camera_capture.capture_frame()
    if not frame_b64:
        return "I was unable to access the camera."
    ocr_text = extract_text(frame_b64, language_code=language_code)
    return await analyze(frame_b64, question, "general", session_id, ocr_text=ocr_text)


async def _run_screen_analyze(question: str, session_id: str, language_code: str = "en") -> str:
    from vision.screen import screen_capture
    from vision.ocr import extract_text
    from vision.analyzer import analyze

    screen_b64 = screen_capture.capture_screen()
    if not screen_b64:
        return "I was unable to capture the screen."

    ocr_text = extract_text(screen_b64, language_code=language_code)

    # Detect content type from OCR text
    context = _detect_screen_context(ocr_text)
    return await analyze(screen_b64, question, context, session_id, ocr_text=ocr_text)


# ── Calculate — real Python arithmetic, LLM only narrates ────────────────────
# This is the one intent where the LLM's job is strictly limited to phrasing:
# tools/calculator.py computes the real answer; the LLM is told that exact
# number and told to state it verbatim. Its response is then checked for the
# exact result string — if the LLM drifted (recalculated, rounded
# differently, or just made something up), we retry once with a more
# forceful prompt, and if it STILL drifts, fall back to a plain template
# that is guaranteed correct. Reliability matters more than creative
# phrasing here — see the module docstring for why.

async def _run_calculate_and_narrate(
    text: str,
    session_id: str,
    mode: str,
    language_code: str,
    user_name: str,
) -> Optional[str]:
    from tools.calculator import calculate, extract_math_expression

    expression = extract_math_expression(text)
    if expression is None:
        # classify_intent() already confirmed extraction succeeds before
        # routing here, so this shouldn't normally happen — but if it does
        # (e.g. a race with different text), don't force a calculator
        # response; let the caller fall through to direct_answer instead.
        return None

    calc = calculate(expression)

    if not calc["success"]:
        error = calc["error"] or "I couldn't compute that."
        response = (
            f"That calculation failed, sir: {error}"
            if mode == "professional"
            else f"Hmm, that didn't work: {error}"
        )
        memory.add_message(session_id, "user", text)
        memory.add_message(session_id, "assistant", response)
        return response

    result_str = str(calc["result"])

    augmented_prompt = (
        f"User's math question: {text}\n\n"
        f"The exact computed answer to this math question is {result_str}. "
        f"This number is authoritative and already verified correct by a "
        f"real calculator — state it exactly as {result_str}, digit-for-"
        f"digit, in your response. Do not recalculate, round differently, "
        f"or alter this number in any way. Do not perform your own "
        f"arithmetic — only narrate this result in your own voice."
    )

    narrated = await brain.generate(
        prompt=augmented_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    )
    if result_str in narrated:
        return narrated

    log.warning(
        "Calculate: LLM response did not contain verified result %r for "
        "expression %r — retrying once with a more forceful prompt.",
        result_str, expression,
    )
    forceful_prompt = (
        f"User's math question: {text}\n\n"
        f"The exact computed answer is {result_str}. You MUST include the "
        f"exact text \"{result_str}\" somewhere in your response, "
        f"unmodified. This is a hard requirement, not a suggestion."
    )
    retried = await brain.generate(
        prompt=forceful_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    )
    if result_str in retried:
        return retried

    log.warning(
        "Calculate: LLM still omitted verified result %r for expression %r "
        "after retry — using guaranteed-correct template fallback.",
        result_str, expression,
    )
    fallback = (
        f"The result is {result_str}, sir."
        if mode == "professional"
        else f"The result is {result_str}!"
    )
    memory.add_message(session_id, "user", text)
    memory.add_message(session_id, "assistant", fallback)
    return fallback


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

    # ── calculate: real Python arithmetic, LLM only narrates (never computes) ──
    # Handled separately from the generic tool_result -> single brain.generate()
    # flow below, since it needs its own verify-and-retry loop around the LLM
    # call (see _run_calculate_and_narrate's module-level comment for why).
    if intent == "calculate":
        calc_response = await _run_calculate_and_narrate(
            text, session_id, mode, language_code, user_name,
        )
        if calc_response is not None:
            return calc_response
        # Extraction unexpectedly failed after classify_intent() already
        # confirmed it would succeed — fall through to a normal
        # direct_answer rather than forcing a calculator response.
        intent = "direct_answer"

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
            tool_result = await _run_camera_analyze(text, session_id, language_code)

        elif intent == "screen_analyze":
            tool_result = await _run_screen_analyze(text, session_id, language_code)

        # direct_answer falls through — tool_result stays None

    except Exception as err:
        log.error("Tool execution failed for intent %s: %s", intent, err)
        tool_result = f"Tool encountered an issue: {err}"

    # ── app_open is returned verbatim — never paraphrased by the LLM ──────────
    # tools.app_control.open_app_from_command() already returns a precise,
    # human-readable outcome ("Launching X." / "Could not launch X: <error>").
    # Routing that through brain.generate() for a "natural language" rewrite
    # is exactly what let the LLM fabricate a fake success narrative for apps
    # it never actually launched — so for this intent the tool's own return
    # value IS the response, with no LLM step in between.
    if intent == "app_open" and tool_result is not None:
        memory.add_message(session_id, "user", text)
        memory.add_message(session_id, "assistant", tool_result)
        return tool_result

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
