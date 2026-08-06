"""
core/agent.py — Regex-based intent router, driven by declarative skill files.

Classifies user input into one of several tool intents using plain
`re` pattern matching (NOT LangGraph — `langgraph` is a listed
dependency but is not imported or used anywhere in this module or
elsewhere in the backend). The matching MECHANISM is unchanged from the
original hardcoded version: `re.search()` per pattern, first match (by
priority) wins. What's declarative now is the DATA — every intent's trigger
patterns, handler function, and special-handling flags live in
`backend/skills/*.SKILL.md` files (parsed by `skills/loader.py`), not in a
Python literal in this module. Adding a new tool intent means adding a new
`*.SKILL.md` file — see `skills/README.md`.

Once an intent is classified, the matching skill's handler is executed and,
for most intents, the tool's result is handed to brain.py to phrase a
natural-language response. A skill can opt out of that via two flags (see
`skills/README.md`): `verbatim_response` (the tool's own return value IS the
response, no LLM rewrite — used by `app_open`/`file_open` so a launch/open
failure can never be narrated as a fake success) and `requires_grounding`
(the handler owns its full response and is called with the complete request
context — used by `calculate`'s verify/retry/template-fallback safeguard
against LLM arithmetic drift).
"""

import inspect
import logging
import re
from typing import Any, Optional

from core.brain import brain
from core.memory import memory
from core.vault import vault
from skills.loader import load_skills
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

# ── Skill loading ──────────────────────────────────────────────────────────────
# Loads every backend/skills/*.SKILL.md file once at import time (same timing
# as the old hardcoded _INTENT_PATTERNS build — no per-request cost) and
# sorts by priority. See skills/loader.py and skills/README.md. Adding a new
# tool intent going forward means adding a new *.SKILL.md file, not editing
# this module.
_SKILLS = load_skills()
_SKILLS_BY_ID = {skill.id: skill for skill in _SKILLS}

# app_open's classification pattern has ONE dynamic component, carried over
# unchanged from the original design: it must be built from
# tools.app_control.APP_MAP at runtime so a new app added there becomes
# voice/text-triggerable with zero code changes (the anti-drift design this
# project has relied on since the original multilingual fix pass — see
# skills/app_open.SKILL.md for the full rationale). FOREIGN_APP_ALIASES
# itself is static data and lives in that skill's frontmatter as plain YAML;
# only the ALTERNATION PATTERNS built from live APP_MAP keys stay dynamic
# Python, appended to the loaded skill's pattern list right here.
_app_open_skill = _SKILLS_BY_ID["app_open"]
FOREIGN_APP_ALIASES: dict[str, str] = _app_open_skill.data.get("foreign_aliases", {})

_APP_NAMES_PATTERN = "|".join(
    re.escape(name) for name in sorted(APP_MAP.keys(), key=len, reverse=True)
)
_FOREIGN_APP_ALIASES_PATTERN = "|".join(
    re.escape(name) for name in sorted(FOREIGN_APP_ALIASES.keys(), key=len, reverse=True)
)
_MULTI_OPEN = r"(open|launch|start|abre|abrir|ouvre|ouvrir|öffne|öffnen)"
_MULTI_OPEN_SCRIPT = r"(खोलो|खोलें|खोल|తెరువు|తెరవండి|열어|열다|開いて|開く|打开|افتح)"

_app_open_skill.patterns.extend([
    rf"\bopen\b.*\b({_APP_NAMES_PATTERN})\b",
    rf"\b({_MULTI_OPEN})\b.*\b({_APP_NAMES_PATTERN}|{_FOREIGN_APP_ALIASES_PATTERN})\b",
    # No \b around the app name here (unlike the bounded pattern above):
    # a script-language open verb (e.g. Chinese 打开) is very often
    # written with NO space before the app name that follows it, so the
    # position right after the verb has no \w/non-\w transition — \b
    # would silently fail to match there. Safe to drop: this pattern
    # only fires at all when a non-Latin trigger verb is present, which
    # never spontaneously appears inside ordinary English/Spanish/French
    # text, so there's no new false-positive surface from removing it.
    rf"{_MULTI_OPEN_SCRIPT}.*({_APP_NAMES_PATTERN}|{_FOREIGN_APP_ALIASES_PATTERN})",
    # Object-before-verb order: several supported languages (Hindi,
    # Japanese, Telugu, Korean) are SOV — "कैलकुलेटर खोलो" literally reads
    # "calculator open", app name before the verb — the reverse of
    # English/Spanish/French/Chinese/Arabic word order handled above.
    rf"({_APP_NAMES_PATTERN}|{_FOREIGN_APP_ALIASES_PATTERN}).*{_MULTI_OPEN_SCRIPT}",
])


def classify_intent(text: str) -> str:
    """
    Return the best-matching intent string for *text*.
    Falls back to "direct_answer" if no pattern matches.

    Skill-driven: iterates the Skill objects loaded from
    backend/skills/*.SKILL.md instead of a hardcoded Python list, but the
    matching MECHANISM (`re.search`, first match by priority order wins) is
    unchanged from the original hardcoded classifier.

    "calculate" (the one `trigger_type: function` skill) is checked FIRST,
    ahead of even the conversational guard: extract_math_expression() is
    strict enough (requires actual digits + an operator/function, and
    excludes phone-number/date-shaped text) that it never spuriously fires
    on personal/chitchat text like "what is my name" (no digits) or "how
    much is 5 years in days" (no operator) — so checking it first is safe
    and is what lets genuine arithmetic like "how much is 100*5" reach the
    calculator instead of being swallowed by the "how much (is|are)"
    conversational override below.

    After that, conversational / personal phrases are checked so they never
    accidentally trigger a different tool (e.g. "what is my name" must not
    web-search).
    """
    lower = text.lower()

    # ── Step 1: function-triggered skills (currently just "calculate") ──────
    for skill in _SKILLS:
        if skill.trigger_type == "function":
            trigger_fn = skill.resolve_trigger_fn()
            if trigger_fn(text) is not None:
                return skill.id

    # ── Step 2: conversational guard ────────────────────────────────────────
    for pattern in _CONVERSATIONAL_OVERRIDES:
        if re.search(pattern, lower):
            return "direct_answer"

    # ── Step 3: regex-triggered skills, in priority order ───────────────────
    for skill in _SKILLS:
        if skill.trigger_type != "regex":
            continue
        for pattern in skill.patterns:
            if re.search(pattern, lower):
                return skill.id

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
    from tools.app_control import open_app, open_app_from_command

    # A foreign-language generic-word app name (e.g. Spanish "calculadora")
    # won't be recognized by open_app_from_command()'s own English/brand-name
    # parsing — resolve it to its canonical APP_MAP key here first. Brand
    # names (Spotify, Chrome, ...) are unaffected and still go through the
    # normal English-oriented parser below.
    lower = text.lower()
    for alias in sorted(FOREIGN_APP_ALIASES.keys(), key=len, reverse=True):
        if alias in lower:
            return open_app(FOREIGN_APP_ALIASES[alias])

    return open_app_from_command(text)


async def _run_file_open(text: str) -> str:
    from tools.app_control import open_file_from_command
    return open_file_from_command(text)


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


# ── Datetime — real system-clock facts, LLM only narrates ────────────────────
# Same shape as _run_calculate_and_narrate above: tools/datetime_tool.py
# computes the real answer (current date/time from the local system clock,
# or a real day-count via dateparser), the LLM is told the exact fact and
# told to narrate it, its response is checked for grounding anchors, and it
# gets one forceful retry before falling back to a guaranteed-correct
# template. The one deliberate difference from calculate's verification:
# see tools/datetime_tool.py's get_current_datetime_fact() docstring for why
# it checks digit-only anchors rather than an exact string match.

async def _run_datetime_and_narrate(
    text: str,
    session_id: str,
    mode: str,
    language_code: str,
    user_name: str,
) -> Optional[str]:
    from tools.datetime_tool import (
        days_until,
        extract_days_until_target,
        get_current_datetime_fact,
    )

    target = extract_days_until_target(text)

    if target is not None:
        calc = days_until(target)
        if not calc["success"]:
            error = calc["error"] or "I couldn't work that out."
            response = (
                f"I couldn't determine that, sir: {error}"
                if mode == "professional"
                else f"Hmm, I couldn't figure that out: {error}"
            )
            memory.add_message(session_id, "user", text)
            memory.add_message(session_id, "assistant", response)
            return response

        days, target_date = calc["days"], calc["target_date"]
        if days == 0:
            fact = f"today, {target_date}"
        elif days == 1:
            fact = f"tomorrow, {target_date}"
        elif days > 0:
            fact = f"{days} days from now, on {target_date}"
        else:
            fact = f"{abs(days)} days ago, on {target_date}"
        anchors = calc["anchors"]
    else:
        fact, anchors = get_current_datetime_fact()

    augmented_prompt = (
        f"User's date/time question: {text}\n\n"
        f"The exact, authoritative answer (from the real system clock, not "
        f"your training data) is: {fact}. State this accurately in your "
        f"own natural voice. You must include the digits "
        f"{' and '.join(anchors)} somewhere in your response, unmodified, "
        f"as confirmation you used the real value provided above rather "
        f"than guessing."
    )

    def _grounded(response: str) -> bool:
        return all(anchor in response for anchor in anchors)

    narrated = await brain.generate(
        prompt=augmented_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    )
    if _grounded(narrated):
        return narrated

    log.warning(
        "Datetime: LLM response did not contain grounding anchors %r for "
        "fact %r — retrying once with a more forceful prompt.",
        anchors, fact,
    )
    forceful_prompt = (
        f"User's date/time question: {text}\n\n"
        f"The exact, authoritative answer is: {fact}. You MUST include the "
        f"exact digits {' and '.join(anchors)} somewhere in your response, "
        f"unmodified. This is a hard requirement, not a suggestion."
    )
    retried = await brain.generate(
        prompt=forceful_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    )
    if _grounded(retried):
        return retried

    log.warning(
        "Datetime: LLM still omitted grounding anchors %r for fact %r "
        "after retry — using guaranteed-correct template fallback.",
        anchors, fact,
    )
    fallback = (
        f"It's {fact}, sir." if mode == "professional" else f"It's {fact}!"
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

    # ── Durable vault: record this turn on every return path below ─────────────
    # Centralized here (not duplicated in chat.py/voice.py) since /chat, /voice,
    # and the wake-word follow-up capture all funnel through run_agent(). Never
    # raises — vault.record_turn() self-guards, so a vault write failure can
    # never break a chat response.
    def _record(response: str) -> str:
        vault.record_turn(
            session_id=session_id,
            user_message=text,
            user_language=language_code,
            assistant_response=response,
            mode=mode,
            intent=intent,
        )
        return response

    # ── Cross-session recall: cheap, scoped, gated on short in-session history ─
    # Only bother looking up the vault when this session doesn't already have
    # real context (a fresh session, or one that's barely started) — matches
    # "new session or insufficient context" from the design, and doubles as
    # the performance cap (skipped entirely on any session with real history).
    vault_context = ""
    if len(memory.get_history(session_id)) < 2:
        vault_context = vault.get_context_for_query(text)

    # ── requires_grounding skills: handler owns its full response ──────────────
    # "calculate" is the only skill with this flag today, but the check is
    # generic (any future skill needing the same verify/retry/template-
    # fallback anti-hallucination pattern can reuse it by setting the flag —
    # see _run_calculate_and_narrate's module-level comment for what that
    # pattern actually does). Handled separately from the generic
    # tool_result -> single brain.generate() flow below, and deliberately
    # NOT given vault_context — its prompt is tightly controlled for the
    # grounding safeguard and must not be perturbed by extra context.
    grounded_skill = _SKILLS_BY_ID.get(intent)
    if grounded_skill is not None and grounded_skill.flags.get("requires_grounding"):
        grounding_handler = grounded_skill.resolve_handler()
        grounded_response = await grounding_handler(
            text, session_id, mode, language_code, user_name,
        )
        if grounded_response is not None:
            return _record(grounded_response)
        # Extraction unexpectedly failed after classify_intent() already
        # confirmed it would succeed — fall through to a normal
        # direct_answer rather than forcing a calculator response.
        intent = "direct_answer"

    tool_result: str | None = None
    dispatch_skill = _SKILLS_BY_ID.get(intent)

    try:
        if dispatch_skill is not None:
            handler_fn = dispatch_skill.resolve_handler()
            # Every handler function takes a PREFIX of (text, session_id,
            # language_code), in that exact order, as positional arguments —
            # e.g. _run_web_search(text), _run_smart_home(text, session_id),
            # _run_camera_analyze(question, session_id, language_code=...).
            # Dispatching by POSITION (not by matching parameter names)
            # reproduces every original hardcoded call site exactly, even
            # where a handler's first parameter isn't literally named
            # "text" (camera/screen name it "question").
            positional_context = (text, session_id, language_code)
            param_count = len(inspect.signature(handler_fn).parameters)
            tool_result = await handler_fn(*positional_context[:param_count])
        # direct_answer (no matching skill) falls through — tool_result stays None

    except Exception as err:
        log.error("Tool execution failed for intent %s: %s", intent, err)
        tool_result = f"Tool encountered an issue: {err}"

    # ── verbatim_response skills are returned as-is — never paraphrased ───────
    # tools.app_control.open_app_from_command()/open_file_from_command()
    # already return a precise, human-readable outcome ("Launching X." /
    # "Could not launch X: <error>" / "Opening X." / "File not found: X").
    # Routing that through brain.generate() for a "natural language" rewrite
    # is exactly what let the LLM fabricate a fake success narrative for apps
    # (or files) it never actually opened — so for these skills the tool's
    # own return value IS the response, with no LLM step in between. Today
    # only app_open/file_open set this flag, but any future skill can opt in
    # the same way.
    if (
        dispatch_skill is not None
        and dispatch_skill.flags.get("verbatim_response")
        and tool_result is not None
    ):
        memory.add_message(session_id, "user", text)
        memory.add_message(session_id, "assistant", tool_result)
        return _record(tool_result)

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

    if vault_context:
        augmented_prompt = f"{vault_context}\n\n{augmented_prompt}"

    return _record(await brain.generate(
        prompt=augmented_prompt,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
        user_name=user_name,
    ))
