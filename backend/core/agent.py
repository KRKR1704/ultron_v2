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

# Non-English words for generic (non-brand-name) apps in APP_MAP — most app
# names in APP_MAP are brand names that don't change across languages
# (Spotify, Chrome, Discord, ...), but a handful of generic-word apps
# (calculator, notepad, terminal, paint) genuinely translate. Maps a foreign
# word -> canonical APP_MAP key, used both to extend app_open's
# classification pattern below AND (in _run_app_open) to resolve the actual
# app to launch, since tools.app_control.open_app_from_command() itself only
# recognizes English/brand names.
FOREIGN_APP_ALIASES: dict[str, str] = {
    # Spanish
    "calculadora": "calculator", "bloc de notas": "notepad", "terminal": "terminal",
    # French
    "calculatrice": "calculator", "bloc-notes": "notepad",
    # German
    "taschenrechner": "calculator", "notizblock": "notepad",
    # Hindi
    "कैलकुलेटर": "calculator",
    # Korean
    "계산기": "calculator",
    # Japanese
    "電卓": "calculator", "計算機": "calculator",
    # Chinese
    "计算器": "calculator",
    # Arabic
    "الآلة الحاسبة": "calculator", "الحاسبة": "calculator",
}
_FOREIGN_APP_ALIASES_PATTERN = "|".join(
    re.escape(name) for name in sorted(FOREIGN_APP_ALIASES.keys(), key=len, reverse=True)
)

# ── Multilingual trigger-word alternations ────────────────────────────────────
# Reuses the technique already proven for mode-switch detection
# (api/routes/chat.py's _MODE_SWITCH_PATTERNS): plain keyword/phrase
# regexes per supported language, ADDED alongside the existing English
# patterns below rather than replacing them — English detection is
# unaffected. Covers the project's actual supported-language list per
# multilingual/language_detector.py's _TEXT_SUPPORTED_LANGUAGES:
# en, hi, es, fr, te, ko, ja, zh, ar (German included too, matching the
# precedent set by chat.py's own mode-switch patterns).
#
# Split into two groups per category:
#   - "latin" words (English, Spanish, French, German): plain Latin
#     alphabet, safe to wrap in \b...\b.
#   - "script" words (Hindi, Telugu, Korean, Japanese, Chinese, Arabic):
#     matched as plain unanchored substrings instead of \b...\b. Two
#     independent reasons, verified directly against Python's `re` engine
#     before relying on this:
#       1. Japanese/Chinese write consecutive words with NO spaces between
#          them, so \bWORD\b fails to match a trigger word sitting directly
#          against the next word (the normal case in a real sentence) —
#          there is no transition to a non-word character between them.
#       2. Hindi/Telugu (Devanagari/Telugu scripts) commonly end words in
#          a dependent vowel sign ("matra", Unicode category Mn, combining
#          mark) — e.g. खोलो, खोजो. \w does NOT include combining marks, so
#          \b silently fails to find a boundary between a trailing matra
#          and a following space (Mn is non-word, space is non-word — no
#          transition). Confirmed by direct testing: re.search(r"\bखोजो\b",
#          "मौसम खोजो") returns None, while re.search(r"खोजो", ...) matches.
_MULTI_OPEN = r"(open|launch|start|abre|abrir|ouvre|ouvrir|öffne|öffnen)"
_MULTI_OPEN_SCRIPT = r"(खोलो|खोलें|खोल|తెరువు|తెరవండి|열어|열다|開いて|開く|打开|افتح)"
_MULTI_SEARCH = r"(search|busca|buscar|cherche|chercher|recherche|suche)"
_MULTI_SEARCH_SCRIPT = r"(खोजो|खोजें|ढूंढो|ढूंढें|వెతకు|검색|検索|搜索|ابحث)"
_MULTI_TURN_ON = r"(turn on|enciende|encender|allume|allumer|einschalten)"
_MULTI_TURN_ON_SCRIPT = r"(चालू करो|जलाओ|వెలిగించు|켜|つけて|点けて|شغل)"
_MULTI_TURN_OFF = r"(turn off|apaga|apagar|éteins|éteindre|ausschalten)"
_MULTI_TURN_OFF_SCRIPT = r"(बंद करो|ఆపు|꺼|消して|أطفئ)"
_MULTI_LIGHTS = r"(lights?|luces|lumières|lichter)"
_MULTI_LIGHTS_SCRIPT = r"(लाइट|रोशनी|దీపాలు|불|أضواء)"
_MULTI_FILE_FOLDER = r"(file|folder|directory|archivo|carpeta|dossier|fichier|ordner|datei)"
_MULTI_FILE_FOLDER_SCRIPT = r"(फ़ाइल|फोल्डर|폴더|파일|ファイル|フォルダ|文件|文件夹|ملف|مجلد)"
_MULTI_MEETING = r"(meeting|reunión|reunion|agenda|cita|réunion|rendez-vous|termin|besprechung)"
_MULTI_MEETING_SCRIPT = r"(बैठक|मीटिंग|कार्यक्रम|회의|会議|会议|اجتماع)"
_MULTI_TASK = r"(remind me|task|recuérdame|recuerdame|tarea|pendiente|rappelle-moi|tâche|tache|erinnere mich|aufgabe)"
_MULTI_TASK_SCRIPT = r"(याद दिलाओ|टास्क|할일|タスク|リマインド|مهمة|تذكير)"
_MULTI_CAMERA = r"(camera|cámara|camara|caméra|kamera)"
_MULTI_CAMERA_SCRIPT = r"(कैमरा|카메라|カメラ|摄像头|相机|كاميرا)"
_MULTI_SCREEN = r"(screen|pantalla|écran|ecran|bildschirm)"
_MULTI_SCREEN_SCRIPT = r"(स्क्रीन|화면|画面|屏幕|الشاشة)"

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
        rf"\b({_MULTI_SEARCH})\b", _MULTI_SEARCH_SCRIPT,   # multilingual search verbs
    ]),
    ("browser_open", [
        r"\bopen\b.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)",
        r"\bgo to\b", r"\bpull up\b", r"\bnavigate to\b",
        r"\bsearch youtube\b", r"\bsearch reddit\b", r"\bsearch google\b",
        rf"\b({_MULTI_OPEN})\b.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)",
        rf"{_MULTI_OPEN_SCRIPT}.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)",
    ]),
    ("app_open", [
        rf"\bopen\b.*\b({_APP_NAMES_PATTERN})\b",
        r"\blaunch\b", r"\bstart\b.*(app|application|program)",
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
    ]),
    ("file_open", [
        r"\bopen\b.*\b(the\s+)?(file|folder|directory)\b",
        r"\bshow\s+me\b.*\b(the\s+)?file\b",
        r"\bopen\b.*\bmy\s+(downloads?|desktop|documents?)\b",
        r"\bopen\b.*\.(txt|pdf|docx?|xlsx?|pptx?|csv|jpe?g|png|py|js|json|md|zip|rtf)\b",
        rf"\b({_MULTI_OPEN})\b.*\b({_MULTI_FILE_FOLDER})\b",
        rf"({_MULTI_OPEN_SCRIPT}|{_MULTI_OPEN}).*({_MULTI_FILE_FOLDER_SCRIPT})",
    ]),
    ("type_text", [
        r"\btype\b", r"\bwrite this\b", r"\benter this\b", r"\bpaste\b",
    ]),
    ("smart_home", [
        r"\bturn on\b", r"\bturn off\b", r"\blights?\b", r"\bthermostat\b",
        r"\btemperature\b", r"\bfan\b", r"\bplug\b", r"\bswitch\b",
        r"\bdim\b", r"\bbrighten\b",
        rf"\b({_MULTI_TURN_ON})\b", rf"\b({_MULTI_TURN_OFF})\b", rf"\b({_MULTI_LIGHTS})\b",
        _MULTI_TURN_ON_SCRIPT, _MULTI_TURN_OFF_SCRIPT, _MULTI_LIGHTS_SCRIPT,
    ]),
    ("calendar", [
        r"\bschedule\b", r"\bmeeting\b", r"\bcalendar\b", r"\bappointment\b",
        r"\bevent\b", r"\bbook\b.*\btime\b",
        rf"\b({_MULTI_MEETING})\b", _MULTI_MEETING_SCRIPT,
    ]),
    ("tasks", [
        r"\btask\b", r"\bremind me\b", r"\bto[- ]do\b", r"\badd to my list\b",
        r"\bcomplete\b.*\btask\b", r"\bfinish\b.*\btask\b", r"\blist.*tasks?\b",
        rf"\b({_MULTI_TASK})\b", _MULTI_TASK_SCRIPT,
    ]),
    ("camera_analyze", [
        r"\bwhat do you see\b", r"\blook at this\b", r"\banalyze this\b",
        r"\bwhat's in front\b", r"\bwhat am i holding\b", r"\bcamera\b",
        rf"\b({_MULTI_CAMERA})\b", _MULTI_CAMERA_SCRIPT,
    ]),
    ("screen_analyze", [
        r"\bwhat'?s on (the )?screen\b", r"\bexplain this\b",
        r"\bwhat am i looking at\b", r"\bread (the )?screen\b",
        r"\bscreen\b",
        rf"\b({_MULTI_SCREEN})\b", _MULTI_SCREEN_SCRIPT,
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

        elif intent == "file_open":
            tool_result = await _run_file_open(text)

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

    # ── app_open / file_open are returned verbatim — never paraphrased ────────
    # tools.app_control.open_app_from_command()/open_file_from_command()
    # already return a precise, human-readable outcome ("Launching X." /
    # "Could not launch X: <error>" / "Opening X." / "File not found: X").
    # Routing that through brain.generate() for a "natural language" rewrite
    # is exactly what let the LLM fabricate a fake success narrative for apps
    # (or files) it never actually opened — so for these intents the tool's
    # own return value IS the response, with no LLM step in between.
    if intent in ("app_open", "file_open") and tool_result is not None:
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
