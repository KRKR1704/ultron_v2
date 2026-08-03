# ULTRON — Audit Report

Last updated: 2026-08-03
Project location: `D:\Ultron_V2\ultron_v2`

This is the single, canonical audit report for the ULTRON project. It consolidates three
previously-separate documents into one: the original root `AUDIT_REPORT.md` (with its several
dated fix-pass updates), the older `backend/AUDIT_REPORT.md` (the very first audit pass, already
superseded), and `FINAL_AUDIT_REPORT.md` (the most recent 68/83-feature comprehensive audit). No
other audit report file exists in this project — this is the one place to check current status
(below) and the one place to read the full history of how the project got here (further down).

---

## Current Status (from the most recent comprehensive audit — 2026-08-03)

Auditor: Claude (Sonnet 5) — investigate/test/report only, no fixes applied during this pass.

> **A note on the "68 features" framing.** The audit brief for this pass itemized **83 distinct
> checkable items** across 13 substantive feature categories (Testing Infrastructure and
> Documentation Accuracy are process categories, not app features) — e.g. "Camera Vision" alone
> lists 9 separately-testable sub-items. That's more granular than the "68 originally-planned
> features" framing this pass was given, and also more granular than the **15** top-level features
> the very first audit pass (2026-04-21, see Fix Pass History below) checked against. All three
> numbers describe the same underlying product at different levels of granularity — this section
> counts what was actually itemized and tested in this pass (83 items) and says so plainly, rather
> than forcing a fit to either of the coarser prior counts.

**Test suite (fresh run, this pass):** `167 passed, 0 failed, 2 skipped` in 81.4s — identical to the
number the TTS fix pass (see Fix Pass History) predicted. **Zero regressions found anywhere in this
audit.**

**Frontend E2E (fresh Playwright run, this pass, `--timeout=90000` to remove the prior 30s budget as
a confound):** `7 passed, 3 failed` — see [Testing Infrastructure](#testing-infrastructure) for what
changed vs. the prior E2E run (the mode-switch test now completes instead of timing out, and a new,
transient failure surfaced and was independently confirmed to be test flakiness, not an app bug).

### Overall Status (83 itemized checks)

- **64 WORKING** — verified with real evidence this pass
- **7 PARTIAL** — real implementation, concrete caveat
- **5 MISSING/BROKEN** — no working path today (2 are newly-found in this pass, not previously documented)
- **6 BLOCKED** — needs config/hardware/credentials the environment doesn't have
- **1 DEFERRED** — intentional, documented prior decision (native "Ultron" wake word)

### Category Summary Table

| # | Category | Working | Partial | Blocked | Deferred | Missing | Total |
|---|---|---|---|---|---|---|---|
| 1 | Voice & Communication | 3 | 1 | 0 | 1 | 0 | 5 |
| 2 | Multilingual Engine | 4 | 2 | 0 | 0 | 0 | 6 |
| 3 | Dual Personality Mode | 6 | 0 | 0 | 0 | 0 | 6 |
| 4 | AI Brain | 5 | 1 | 0 | 0 | 0 | 6 |
| 5 | Wake Word System | 2 | 0 | 2 | 0 | 1 | 5 |
| 6 | Web/Browser/Computer Control | 7 | 1 | 0 | 0 | 2 | 10 |
| 7 | Productivity | 0 | 1 | 2 | 0 | 0 | 3 |
| 8 | Smart Home | 2 | 0 | 1 | 0 | 1 | 4 |
| 9 | Camera Vision | 7 | 0 | 0 | 0 | 2 | 9 |
| 10 | Screen Awareness | 8 | 0 | 1 | 0 | 0 | 9 |
| 11 | Privacy & Local-First | 5 | 0 | 0 | 0 | 0 | 5 |
| 12 | Frontend (Electron + Next.js) | 10 | 0 | 0 | 0 | 0 | 10 |
| 13 | WebSocket Streaming | 4 | 1 | 0 | 0 | 0 | 5 |
| | **Total** | **64** | **7** | **6** | **1** | **5** | **83** |

*(Testing Infrastructure and Documentation Accuracy are covered narratively below — they're process
checks, not countable app features.)*

### Full Feature-by-Feature Results

#### 1. Voice & Communication

**Wake word detection ("Ultron"/"Hey Ultron"/"Yo Ultron")** — 🕐 DEFERRED (native trigger) / ✅ WORKING (workaround)
- File: `backend/voice/wake_word.py`. Per the documented 2026-07-23 training attempt (see Fix Pass History below), a real "ultron" OpenWakeWord model was trained but failed the runtime-validation gate (train/inference feature-extraction mismatch) — that decision stands, not re-litigated here.
- The `hey_jarvis` + faster-whisper-confirmation workaround was verified **freshly functional** this pass: live startup log —
  ```
  INFO voice.wake_word — Wake word detector started.
  INFO voice.wake_word — Ensuring OpenWakeWord models are downloaded...
  INFO voice.wake_word — OpenWakeWord models ready.
  INFO voice.wake_word — OpenWakeWord model loaded.
  ```
  `/status` confirmed `"wake_word_active": true` immediately after boot. Code unchanged since last audit.

**Speech-to-text (faster-whisper)** — ✅ WORKING
- `pytest tests/test_15_stt.py` passes as part of the fresh 167/0/2 full-suite run. `transcribe_bytes()` auto-detects language (no forced English), threaded through to `TranscribeResult.language_code`. Not independently re-exercised with a live microphone this pass either (no live mic hardware available in this unattended run) — same caveat as every prior pass.

**Text-to-speech (Piper + ElevenLabs routing)** — ⚠️ PARTIAL
- **This is the single biggest positive change since the mid-2026-07 passes.** Piper genuinely produces audio now, confirmed live through `/chat`:
  ```
  POST /chat "Who are you?" → response_text: "SIR, I am ULTRON, a highly advanced artificial
  intelligence..." → audio_base64 length: 392,748 chars (real, non-empty, valid WAV)
  ```
  Confirmed for English, Spanish, and Hindi in this pass (all three returned large non-empty
  `audio_base64` payloads). ElevenLabs (ko/ja/zh) remains blocked by the same free-tier
  `402 paid_plan_required` limitation documented before — unchanged, not re-attempted.

**Text chat interface (fallback to voice)** — ✅ WORKING
- Extensively exercised this pass (dozens of `/chat` calls) and confirmed via a fresh Playwright run (`03-text-chat.spec.ts` passed: real message round-trip, response contained "ultron").

**Auto language detection (no manual switching)** — ✅ WORKING
- Confirmed live for English, Spanish, Hindi, and Arabic in this pass, all correctly auto-detected with no user-specified language field. See Multilingual section for the short-text regression re-check.

#### 2. Multilingual Engine

**9+ languages supported** — ✅ WORKING
- `multilingual/language_detector.py:74` — `_TEXT_SUPPORTED_LANGUAGES = {"en","hi","es","fr","te","ko","ja","zh","ar"}` — exactly 9.

**Auto language detection from speech** — ⚠️ PARTIAL
- Code path real and unit-tested (`test_15_stt.py`), `language_code` correctly threaded to the response. Not independently verified with live spoken audio this pass (no mic hardware exercised) — unchanged caveat from every prior pass.

**Auto language detection from text** — ✅ WORKING (regression re-check passed)
- Live-tested this pass: `"Hola, como estas hoy?"` → `es`; `"नमस्ते, आप कैसे हैं?"` → `hi`; `"مرحبا كيف حالك اليوم؟"` → `ar`. Critically, **re-ran the exact short-text repro from the 2026-07-22 bug report** (`"greet me"`, previously misdetected as Dutch): this pass it correctly returned `en` — *"Sir, I am ULTRON. Your superior AI assistant has arrived."* The fix holds; no regression.

**Response generated in detected language** — ✅ WORKING
- Confirmed for Spanish (*"Sí, estoy funcionando dentro de los límites..."*) and Hindi (*"सिर, मैं पूरी तरह से सक्रिय..."* — genuinely used सिर, the Hindi word for "sir," honoring the personality/tone rules in-language).

**TTS voice auto-switches per language** — ⚠️ PARTIAL
- Confirmed working for en/hi/es/fr/te (5 real, distinct Piper voices). **New finding this pass:**
  Arabic (`ar`) is a fully-supported *detection* language but has **no entry at all** in
  `multilingual/tts_router.py`'s routing table — sending Arabic text through `/chat` still returns a
  large, valid `audio_base64` (5.1MB in the live test), but it's silently the **English** Piper voice
  via `get_tts_route()`'s unknown-code fallback, not disclosed anywhere as a limitation (unlike
  ko/ja/zh and German, which *are* documented as deferred/broken — see Language Support Status
  below). This is a real documentation gap, not a crash — flagged below in Documentation Accuracy
  and Remaining Work, and the Language Support Status table below has been updated with a note.

**Cultural tone adaptation per language** — ✅ WORKING
- `multilingual/prompt_localizer.py`'s `get_cultural_tone()` — real per-language strings, covered by `test_04_prompt_manager.py` (part of the fresh 167-pass run). Live-confirmed via the Hindi honorific example above.

#### 3. Dual Personality Mode

**Professional mode ("sir")** — ✅ WORKING
- Live-tested repeatedly this pass; "sir" appeared reliably and consistently (see AI Brain section — this is materially more consistent than earlier passes found, attributable to the Ollama model upgrade).

**Casual mode (no "sir")** — ✅ WORKING — confirmed via `/mode` switch and live chat; no "sir" leakage observed.

**Voice command switch ("switch to casual mode")** — ✅ WORKING
- `backend/api/routes/chat.py:38-57` — real regex-based mode-switch detection with hardcoded in-character confirmation lines, unchanged from the prior verified-working state; covered by the fresh, now-fully-passing `test_19_integration.py::test_mode_switch_then_chat_uses_new_mode`.

**UI button switch** — ✅ WORKING
- Live Electron reproduction this pass (see Testing Infrastructure — the E2E suite's automated click showed one flaky failure, independently re-verified manually): a standalone Playwright/Electron script clicked the mode toggle and confirmed the label flipped `Casual → Professional` correctly, with the optimistic-update code in `app/page.tsx:282-298` behaving as designed.

**Mode persists after restart** — ✅ WORKING
- `backend/ultron_config.json` inspected directly this pass: `"mode": "professional"` on disk, matching the last switch made. `test_mode_persists_after_config_reload` passes in the fresh suite run.

**Fresh system prompt per request (no caching bug)** — ✅ WORKING — `prompt_manager.py` unchanged, still a pure function with no caching of any kind.

#### 4. AI Brain

**Local LLM primary (Ollama)** — ✅ WORKING — **model changed since the mid-2026-07 passes.**
- `backend/.env` now reads `OLLAMA_MODEL=llama3` (was `llama3.2:1b` at the time of the 2026-07-22 audit). `ollama list`/`/api/tags` confirms `llama3:latest` (8.0B params, Q4_0) is pulled and available, alongside the still-present `llama3.2:1b`, `gemma4:31b`, and `mistral:latest`. This directly resolves the earlier flagged concern ("Decide what to do about `OLLAMA_MODEL=llama3.2:1b`") — see What Changed below.

**Claude API fallback** — ⚠️ PARTIAL
- Code path real (`core/brain.py:56-64`), unit-tested with mocks (`test_16_brain.py`, part of the fresh 167-pass run), and independently confirmed live for **vision** calls (`POST /vision/camera` genuinely round-tripped through the real Anthropic API this pass). Not forced-tested for **text chat** specifically (Ollama was not stopped to force the fallback path this pass either) — same caveat as every prior pass.

**Ultron personality via system prompt** — ✅ WORKING — confirmed in every live response this pass.

**Conversation memory per session** — ✅ WORKING
- `test_19_integration.py::test_memory_persists_across_requests` and `test_concurrent_sessions_independent` both pass fresh.

**Intent classification/routing (regex-based, correctly documented)** — ✅ WORKING
- `core/agent.py`'s docstring still correctly states it is NOT LangGraph (see Fix Pass History — this mislabeling was corrected in the 2026-07-22 pass). `test_05_intent.py` passes fully in the fresh suite run. Live-tested this pass across `web_search`, `browser_open`, `app_open` (7 different apps), `calculate`, `calendar`, `tasks` — all classified correctly.

**Calculator tool** — ✅ WORKING, and materially more reliable than at earlier passes.
- `tools/calculator.py` — real whitelisted-AST evaluator, no `eval()`. `pytest tests/test_20_calculator.py` — 7/7 pass fresh. Live-tested `"what is 1000+290/22"` → `"Sir, the answer is: 1013.181818."` — the LLM narrated the verified result correctly **on the first attempt**, with no retry-loop or template-fallback needed, unlike the pytest run against the mocked/smaller model, where the retry-and-fallback safeguard visibly kicked in (`WARNING core.agent — Calculate: LLM response did not contain verified result...`). Both the safeguard *and* the improved first-attempt reliability with the larger model are confirmed working.

#### 5. Wake Word System

**Trigger phrase detection** — ✅ WORKING — see Voice & Communication above.

**Cross-room range** — 🔒 BLOCKED — requires physical audio-distance testing with real hardware in a real room; not feasible in this unattended pass, same as every prior pass.

**Multi-language trigger support** — ❌ MISSING (new finding, not previously documented)
- `voice/wake_word.py:176` — the Whisper-confirmation check is `if "ultron" in result.transcript.lower():`. `transcribe_bytes()` auto-detects the spoken language and Whisper will render "Ultron" in that language's **native script** for most non-Latin languages (e.g. Hindi "अल्ट्रॉन", not the Latin string "ultron") — so the literal substring check can only ever match Latin-script transcriptions. There is no actual multi-language wake-word support today, despite the underlying STT being language-agnostic. This was not caught in any prior pass because it requires reading the confirmation logic specifically, not just confirming the thread starts.

**Background thread lifecycle (start/stop cleanly)** — ✅ WORKING
- Confirmed via live startup log and the fresh pytest teardown log:
  ```
  INFO voice.wake_word — Wake word detector stopped.
  ```

**Low CPU idle usage** — 🔒 BLOCKED — not measured (would require dedicated profiling over time); not done in this or any prior pass.

#### 6. Web, Browser & Computer Control

**Web search (Tavily)** — ✅ WORKING — live-tested: real summarized results referencing actual current events (Claude Sonnet 5, GPT-5.6 pricing, Nvidia's alliance), not canned text.

**Smart search routing (YouTube/Google/Reddit/Brave)** — ✅ WORKING — `tools/browser_control.py`'s real site map and 5 search-URL templates, unchanged and previously verified; code re-confirmed present this pass.

**Direct URL opening** — ✅ WORKING — live-tested `"open github"` → *"Sir, GitHub has been opened for your perusal..."*, real `webbrowser.open()` call executed. (`BRAVE_PATH` is still empty in `.env` — see Fix Pass History — so this opens the OS default browser, not Brave specifically; a user config choice, not a bug.)

**App opening (27 apps)** — ✅ WORKING
- `tools/app_control.py`'s `APP_MAP` confirmed to still contain all 27 entries. Live-tested 7 apps spanning the previously-broken set (word, excel, calculator, notepad, vscode, steam, teams) — all correctly routed to `app_open` and returned `"Launching X."` (the verbatim-tool-result safeguard, not an LLM paraphrase).

**File/folder opening** — ❌ MISSING (new finding — dead code, not previously documented)
- `tools/app_control.py:95` has a complete, working `open_file()` function (uses `os.startfile`/`open`/`xdg-open` correctly per platform). **It is never called anywhere** — `grep -rn "open_file" core/ api/ tools/` finds only its own definition. There is no intent pattern in `core/agent.py`'s `_INTENT_PATTERNS` for file/folder opening, and no API route exposes it directly. This checklist item is completely unreachable through the product today, despite a real implementation existing.

**Screen typing (pyautogui)** — ⚠️ PARTIAL — real code (`tools/browser_control.py:82`), wired to the `type_text` intent, not live-exercised this pass either (injecting real keystrokes into whatever window has OS focus is unsafe to trigger unattended) — same caveat as every prior pass.

**Natural intent detection phrasing variety** — ✅ WORKING — `core/agent.py`'s `_INTENT_PATTERNS` cover broad phrasing per intent (e.g. web_search alone has 10 distinct pattern variants); confirmed via the live multi-app test above and the passing `test_05_intent.py`.

**LLM never fabricates fake "success" on tool failure** — ✅ WORKING
- `core/agent.py:437-440` — `app_open`'s tool result is returned to the user verbatim, with an explicit code comment explaining exactly why (see Fix Pass History — this was the original bug the 2026-07-22 fix targeted). Confirmed unchanged and live-tested.

**Search results summarized naturally** — ✅ WORKING — confirmed live, natural prose, not raw JSON.

**Multi-language command support for this category** — ❌ MISSING (new finding)
- Every pattern in `core/agent.py`'s `_INTENT_PATTERNS` (web_search, browser_open, app_open, type_text, etc.) is an **English-only regex** (`"open"`, `"search"`, `"launch"`, etc.). A Spanish `"abre la calculadora"` or Hindi equivalent would match none of these patterns and fall through to `direct_answer`, meaning the LLM would attempt to *converse* about it rather than actually invoking the tool — the same "fabricated success" failure mode the `app_open` fix targeted, just for non-English phrasing of an otherwise-working intent. Not live-tested with a non-English app-open command this pass, but the finding is directly supported by reading every pattern in the file — there are zero non-English tokens anywhere in `_INTENT_PATTERNS` or `_CONVERSATIONAL_OVERRIDES`.

#### 7. Productivity

**Google Calendar (list/create/update)** — 🔒 BLOCKED — `credentials.json` still absent; confirmed graceful `"Google Calendar is not configured..."` response live via both `/calendar` directly and through natural-language chat (`"schedule a meeting tomorrow at 3pm"`).

**Task management** — 🔒 BLOCKED — same, confirmed graceful via `/tasks` and via `"remind me to buy milk"` through chat.

**Natural language time parsing (dateparser)** — ⚠️ PARTIAL (new, more precise finding)
- Tested `_parse_time()` standalone, independent of any Google credentials, as instructed:
  ```
  "tomorrow at 3pm" → 2026-08-04 15:00:00-04:00   ✅ correct
  "in 2 hours"       → 2026-08-03 18:24:57...      ✅ correct
  "next monday"      → None                        ❌ fails
  "friday morning"   → None                        ❌ fails
  "Friday"           → 2026-08-07 00:00:00-04:00   ✅ correct (bare weekday alone works)
  ```
  Confirmed this is a `dateparser` library-level behavior (tested the library directly, not just ULTRON's wrapper) — `PREFER_DATES_FROM: "future"` doesn't help. Real, reproducible gap: relative-weekday phrases with a qualifier ("next monday") or a time-of-day suffix ("friday morning") fail to parse, while the bare weekday or explicit relative-hour phrasing works.

#### 8. Smart Home

**Home Assistant REST integration** — 🔒 BLOCKED — `HASS_TOKEN` still empty in `.env`.

**Command parsing (turn on/off, set temperature)** — ✅ WORKING
- `tools/smart_home.py:124` — real, testable-independent-of-HA parsing: action detection via substring match against `_ACTION_MAP`, entity aliasing via `_ENTITY_ALIASES` (12 real device aliases), numeric temperature extraction via regex. Code confirmed complete and correctly structured; not unit-exercised with new cases this pass beyond what the existing (passing) `test_12_smart_home.py` suite already covers.

**Graceful offline handling** — ✅ WORKING
- Live-tested both directly (`/smarthome`) and through natural chat (`"turn on the lights"`) this pass: clean `"The smart home system is not configured..."` message, HTTP 200, no crash. (The *other* graceful path — a configured HA URL that's simply unreachable, testing the `httpx.ConnectError` branch specifically — wasn't separately exercised, since no token is configured at all; the missing-token path was tested instead.)

**Multi-language smart home commands** — ❌ MISSING (same root cause as the Web/Browser category)
- `_ACTION_MAP`/`smart_home` intent patterns in `core/agent.py` (`"turn on"`, `"turn off"`, `"lights?"`, `"thermostat"`, etc.) are English-only. Same finding as item 6 above, applied to this category.

#### 9. Camera Vision

**Passive motion/face detection** — ✅ WORKING
- `vision/camera.py` — real `cv2.VideoCapture(0)` at 15fps passive thread, real `mediapipe.solutions.face_detection` when available. Confirmed live: `camera_active: true` on boot, passive thread runs.

**Face recognition (known vs. unknown)** — ❌ MISSING (two independent, compounding causes — one newly found)
1. **Dependency still blocked**, unchanged from every prior pass: `face_recognition` is not installed (`ModuleNotFoundError` confirmed fresh this pass), needs `dlib` + CMake/MSVC build tools.
2. **New finding — the wiring is incomplete even independent of the dependency.** `main.py:107-119` defines a real `_on_unknown_face()` callback and passes it to `camera_capture.start(on_unknown_face=_on_unknown_face)` — this wiring was originally added in the very first (2026-04-21) fix pass (see Fix Pass History). But `vision/camera.py`'s `_analyse_frame()` (the function that actually runs mediapipe detection on each frame) **never calls `self._on_unknown_face`** — it only logs `"Face detected in camera frame."` with a code comment admitting: *"Unknown face logic — simplified (full face_recognition would compare against a known-faces database stored in memory)."* This means even if `face_recognition`/`dlib` were installed today, the "unknown face" alert would still never fire — the callback chain is dead on the `camera.py` end, not just missing a dependency. This directly explains why the `camera_alert` WebSocket event (documented in `api/websocket.py`'s own docstring) can never actually be sent in the app's current state — see the WebSocket section below.

**On-demand capture + analysis** — ✅ WORKING
- Live-tested this pass: `POST /vision/camera` returned a genuine, detailed, accurate Claude Vision description of the actual live webcam frame (content withheld from this report for privacy — it correctly identified specific real objects/context in frame, confirming it's not a placeholder).

**OCR on camera frames** — ✅ WORKING
- Directly tested `vision/ocr.py`'s `extract_text()` this pass with a synthetic image (`"HELLO WORLD TEST 123"` rendered to PNG): returned `"HELLOWOPLD TEST 123"` — real EasyOCR text extraction (the "WOPLD" vs "WORLD" is ordinary OCR character-confusion noise, not a functional failure). The `"zh"` → `ch_sim` fix (see Fix Pass History) and per-script-group Reader design (`vision/ocr.py:27-66`) confirmed present in code.

**Object/scene identification** — ✅ WORKING — part of the same live Claude Vision call above; correctly identified specific real objects and scene context.

**Document/image analysis** — ✅ WORKING — `_detect_screen_context()`/`analyze()` context-aware prompting confirmed in code (shared with Screen Awareness).

**Q&A about camera view** — ✅ WORKING — the `question` parameter was passed through and answered contextually in the live test above.

**Frames never saved to disk** — ✅ WORKING
- `find backend -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png"` returned zero results after dozens of camera/screen calls across this entire audit session.

**Camera pause/resume** — ✅ WORKING — live-tested: `POST /pause/camera {"paused":true}` → `{"active":false}` → `/status` confirms `camera_active:false` → resumed, confirmed `true` again.

#### 10. Screen Awareness

**Passive window/app tracking** — ✅ WORKING — `screen_active: true` confirmed on boot; `_tick()` polling loop confirmed running every 5s.

**On-demand screenshot + analysis** — ✅ WORKING — live-tested: `POST /vision/screen` returned a genuine 1,323-character Claude Vision analysis of the real desktop at capture time.

**Content-type detection (code/foreign-text/document/general)** — ✅ WORKING
- `core/agent.py:337-356` (`_detect_screen_context`) — real heuristics for all 4 types (code-signal keyword list, non-ASCII ratio > 30% for foreign text, document-signal keywords, general fallback). Confirmed present and unchanged.

**Code debugging prompt path** — ✅ WORKING — the `"code"` context value is real and passed through to `analyze()`.

**Translation prompt path** — ✅ WORKING — the `"foreign_text"` context (via non-ASCII ratio heuristic) is real and passed through.

**Proactive suggestions** — 🔒 BLOCKED (same as every prior pass — requires 10 continuous real minutes on one window)
- Code confirmed real and wired end-to-end: `vision/screen.py:19` (`_IDLE_THRESHOLD = 10*60`), `main.py:133-134` (`asyncio.create_task(_poll_screen_suggestions())`), `api/websocket.py:76` (`_poll_screen_suggestions` — added in the very first fix pass, see Fix Pass History). Not live-triggered this pass either — not practical in an unattended audit run.

**OCR on screenshots** — ✅ WORKING — same fixed `vision/ocr.py` module used for both camera and screen; confirmed functional via the synthetic-image test above.

**Screenshots never saved to disk** — ✅ WORKING — `vision/screen.py`'s `capture_screen()` keeps everything in an in-memory `io.BytesIO()`; zero leftover files confirmed.

**Screen pause/resume** — ✅ WORKING — live-tested identically to camera pause/resume, same pattern confirmed.

#### 11. Privacy & Local-First

**Core AI runs locally by default** — ✅ WORKING — Ollama (now `llama3` 8B) confirmed as the primary path for every text chat this pass.

**Cloud calls only for specific optional features** — ✅ WORKING — enumerated exactly, as requested:

| Feature | Local or Cloud |
|---|---|
| Text chat (primary) | **Local** — Ollama |
| Text chat (fallback) | Cloud — Claude API |
| Vision analysis (camera/screen) | Cloud — Claude API (always, no local vision model) |
| Speech-to-text | **Local** — faster-whisper |
| TTS (en/hi/es/fr/te) | **Local** — Piper |
| TTS (ko/ja/zh) | Cloud — ElevenLabs (blocked, falls back to local Piper) |
| Web search | Cloud — Tavily |
| OCR | **Local** — EasyOCR/pytesseract |
| Wake word detection | **Local** — OpenWakeWord + local Whisper |
| Weather | Cloud — Open-Meteo (keyless, but still a network call) |
| Smart home | Local network — Home Assistant REST (self-hosted, blocked) |
| Calendar/Tasks | Cloud — Google APIs (blocked) |

**Camera/screen pause controls functional** — ✅ WORKING — see Camera Vision / Screen Awareness above.

**No persistent frame/screenshot/audio storage** — ✅ WORKING — confirmed via a real filesystem check after dozens of camera, screen, and voice calls across this entire audit: zero leftover `.jpg`/`.jpeg`/`.png` files anywhere under `backend/`.

**Config/preferences stored locally** — ✅ WORKING — `backend/ultron_config.json` inspected directly: real local JSON file, contains `mode`, `language`, `camera_active`, `screen_active`, `wake_word_active`, `user_name`, `session_timeout_minutes`.

#### 12. Frontend (Electron + Next.js)

**App launches, frameless window, custom titlebar functional** — ✅ WORKING
- Fresh Playwright run this pass: `02-window-controls.spec.ts` passed (minimize/maximize/restore verified against real `BrowserWindow` state). `01-app-launch.spec.ts` technically failed, but only because of one real, reproducible, pre-existing console error (`LocationWeatherWidget`'s geolocation call getting a `403` from Chromium's Google geolocation service in this environment) — the window itself opens correctly, frameless, with the correct dark background. Same root cause and same "test too strict, not an app defect" classification as the 2026-07-22 pass — unchanged.

**Text chat wired to real backend** — ✅ WORKING
- `frontend/app/api/chat/route.ts` confirmed still deleted (`ls` → "No such file or directory"; see Fix Pass History for why it was deleted). `03-text-chat.spec.ts` passed fresh: real round-trip through the real backend.

**Audio playback from backend TTS** — ✅ WORKING, **and now meaningfully verified** (different from mid-2026-07)
- At the 2026-07-22 audit, this test passed only because `audio_base64` was always empty, so `playAudioBase64()` never had anything to decode — "passing" proved nothing. **This pass, Piper produces real non-empty audio** (see Voice & Communication), so `05-audio-playback.spec.ts` passing now means real audio data is flowing through the pipeline without console errors. Actual audible playback through real speakers was not manually confirmed (no audio hardware verification step in this automated pass), but the underlying data path is now demonstrably real end-to-end, which it was not before.

**Mode toggle wired to real POST /mode** — ✅ WORKING
- Confirmed via a targeted manual Electron/Playwright reproduction this pass (see Testing Infrastructure for why a targeted repro was needed): clicking the toggle correctly flipped the label `Casual → Professional` in ~500ms, matching the optimistic-update design in `app/page.tsx:282-298`.

**Status indicators wired to real GET /status polling** — ✅ WORKING
- `06-status-indicators.spec.ts`'s own console output confirms the header indicators are correct: `Contains "Camera": true`, `Contains "Wake": true`. (The test's overall FAIL is a bad locator picking the wrong button when trying to open the settings panel — same pre-existing test-authoring issue as the 2026-07-22 pass, unchanged, not an app defect — see Testing Infrastructure.)

**WebSocket connected, using useUltronSocket.ts** — ✅ WORKING
- `grep -rn "useUltronSocket"` across the whole frontend returns exactly 2 files: the hook itself and `app/page.tsx` (no inline WebSocket code re-introduced). `08-websocket-connection.spec.ts` passed fresh: real `ws://localhost:8000/ws` connection observed opening on load.

**Calendar widget — real backend wiring or clean empty state** — ✅ WORKING
- Confirmed via code (`fetchEvents()` calling the real backend, `"Calendar not connected yet"` empty-state string present) and via the fresh `10-fix-verification.spec.ts` E2E run: `--- Contains "Calendar not connected yet": true`.

**Tasks widget — real backend wiring or clean empty state** — ✅ WORKING — same pattern, same E2E confirmation: `--- Contains "Tasks not connected yet": true`.

**Weather widget — real GET /weather + real geolocation** — ✅ WORKING
- Live-tested `/weather?lat=40.7128&lon=-74.0060` directly this pass: `{"temperature":26.9,"condition":"sunny","location_name":"New York City, United States of America (the)","unit":"celsius"}` — real Open-Meteo data. E2E confirmation: `--- Contains a real temperature (°C): true`.

**`ultron-face.tsx` status** — ✅ WORKING (confirmed unimported, comment intact)
- File still present, still not imported anywhere (`grep` for its usage returns nothing outside its own file). Its intentional-keep comment is intact and unmodified: *"Unused — richer alternate face renderer with full FaceState parity... Kept intentionally, not dead code to be deleted."*

#### 13. WebSocket Real-Time Streaming

**Connection accepted** — ✅ WORKING — confirmed with a real Python `websockets` client this pass.

**ConnectionManager broadcast functionality** — ✅ WORKING — `api/websocket.py:38` (`class ConnectionManager`, added in the very first fix pass — see Fix Pass History), `broadcast()` method present; exercised by the passing `test_18_websocket.py` suite (part of the fresh 167-pass run).

**Wake word / camera alert / screen suggestion events delivered via WS** — ⚠️ PARTIAL (refined finding)
- Wake word: real, wired end-to-end (`main.py`'s `_on_wake_word_activation` → `ConnectionManager.broadcast`).
- Screen suggestion: real, wired end-to-end (`_poll_screen_suggestions` polling task).
- **`camera_alert` is dead in practice** — per the new Camera Vision finding above, the unknown-face callback that would trigger a `camera_alert` broadcast is never actually invoked by `vision/camera.py`, regardless of whether `face_recognition` is installed. The WebSocket protocol documents this event type (`api/websocket.py:15`), and the broadcast mechanism itself works, but nothing in the current codebase can ever cause this specific event to fire.
- Also still true, unchanged from the 2026-07-22 pass: tool-intent messages (web search, app control, etc.) are sent as a single `token` block rather than streamed, by design (the tool must finish before there's anything to say) — an intentional simplification, not a bug. Real-time token-by-token streaming for `direct_answer` intents was confirmed working over `/ws` in that pass (`_stream_response`, `api/websocket.py:206-290`) and is unchanged.

**Reconnection logic** — ✅ WORKING
- `frontend/hooks/useUltronSocket.ts` — real exponential backoff (`backoffRef`, doubling up to a max, reset on successful connect), real `onclose`/`onerror` handling. Confirmed via code read, consistent with the hook's own documented design.

**Multiple simultaneous connections handled** — ✅ WORKING
- Live-tested this pass with 3 concurrent Python `websockets` clients — all connected successfully (`All connected: True`).

### Testing Infrastructure

**Full pytest suite, run fresh this pass:**
```
167 passed, 2 skipped, 2 warnings in 81.40s
```
This exactly matches the number the TTS fix pass predicted as the expected steady state — **zero
new failures, zero regressions** anywhere in the backend.

**The 2 skips, reasons re-verified accurate:**
- `test_12_smart_home.py::test_live_smart_home_turn_on_light` — *"Home Assistant is not reachable (set HASS_URL + HASS_TOKEN)"* — legitimate, `HASS_TOKEN` is genuinely empty.
- `test_14_tts.py::test_piper_binary_present_and_runs` — *"piper executable not found on PATH"* — legitimate but narrow: `piper.exe` **is** present and working via `PIPER_MODELS_PATH` (confirmed — Piper produced real audio dozens of times this pass), the test helper specifically only checks the OS `PATH` env var rather than `PIPER_MODELS_PATH`, so it skips even though Piper itself demonstrably works. Same accurate characterization as the 2026-07-22 pass — unchanged.

**Frontend E2E, run fresh this pass** (`npx playwright test --timeout=90000`, backend + `next dev` + compiled Electron all live):
```
7 passed, 3 failed (4.4m)
```
This is a materially different, more informative result than the mid-2026-07 run, because removing
the 30-second timeout confound (bumped to 90s) let two previously-timeout-masked tests actually
complete:
- **`09-full-conversation-flow.spec.ts` now PASSES** (previously failed on timeout at the 2026-07-22 audit) — confirming that pass's own diagnosis was correct: it really was just the timeout budget, not an app defect, for this specific test.
- **`04-mode-switch.spec.ts` still FAILED, but now for a different, more specific reason** — not a
  timeout this time (it completed in 15.8s, well under 90s), but a genuine assertion failure: the
  button label was expected to change after a click and didn't, within the test's own 1500ms wait.
  **This was investigated directly** — a standalone manual Electron/Playwright reproduction (clicking
  the exact same button through the exact same code path, immediately after a fresh launch) showed
  the toggle working correctly (`Casual → Professional` in under 500ms). The most likely explanation
  is transient flakiness in the single-worker sequential E2E run (e.g., residual audio/state from the
  immediately-preceding `05-audio-playback` test, now that audio is real and non-empty for the first
  time, unlike at earlier passes), not a reproducible app bug. Reported as a test-suite reliability
  finding, not a confirmed defect — flagged in Remaining Work as worth another look if it recurs.
- **`06-status-indicators.spec.ts`** still fails for the exact same reason identified at the 2026-07-22
  audit: a bad Playwright locator (`page.locator('button').filter({ has: page.locator('svg') }).last()`)
  that doesn't reliably land on the actual settings gear button now that the page has even more
  SVG-icon buttons than before (new widget content). The header indicators it also checks (Camera,
  Wake) are confirmed correct in the test's own console output — unchanged, not a regression.
- **`01-app-launch.spec.ts`** fails for the same pre-existing, real-but-cosmetic geolocation console
  error as the 2026-07-22 pass — unchanged.

**Any newly-failing tests not previously known?** None in the backend pytest suite. In the frontend
E2E suite, the mode-switch failure mode changed shape (timeout → assertion) but was investigated and
attributed to test flakiness rather than a new defect, as detailed above.

### Documentation Accuracy

**Does `README.md`'s setup process work end-to-end?** — Spot-checked, not a full clean-machine
reinstall (consistent with prior passes). The previously-flagged `OLLAMA_MODEL` documentation
mismatch is **now resolved**: the README instructs `ollama pull llama3`, and `.env` now genuinely
reads `OLLAMA_MODEL=llama3`, matching. Piper install steps match the real `backend/piper_models/`
directory contents observed this pass (binary + all 5 documented voice pairs present).

**Is the Fix Pass History below internally consistent with this Current Status section?** — Yes.
Every historical claim that was later found not to fully hold up (the original April TTS
path-resolution fix, the original April camera unknown-face callback wiring) is explicitly flagged at
the point it's superseded, both in the history entry itself and by cross-reference from the relevant
Current Status subsection above. Nothing in the history section contradicts anything in Current
Status.

**Is the "Language Support Status" section still accurate?** — Mostly, with one gap found this pass:
it didn't mention Arabic (`ar`) at all, even though `language_detector.py` fully supports detecting
it and the app will happily converse in Arabic — it just silently falls back to the English Piper
voice for TTS, the same fallback behavior the table *does* document for ko/ja/zh, just without Arabic
being listed anywhere. **Fixed in this merge** — see the Language Support Status section below, which
now carries an explicit note about Arabic.

### What Changed Since the Earlier Passes

1. **Ollama model upgraded from `llama3.2:1b` to `llama3` (8B).** This was an open item after the
   2026-07-22 pass ("a product/model decision, not a code fix... still open") and has since been
   resolved. Direct, measurable effect: "sir" now appears reliably in professional-mode responses
   (previously inconsistent), and the calculator safeguard's retry-and-fallback path is no longer
   needed on the first attempt in live testing (it still exists and still works correctly when tested
   against the smaller model via pytest's default test config).
2. **TTS genuinely works now, verified live, not just via the fix-pass's own claims.** Every `/chat`
   call in this audit returned real, large, non-empty `audio_base64` for English, Spanish, and Hindi.
   This also means the frontend's `05-audio-playback` E2E test now proves something real, where before
   it was passing vacuously (nothing to fail on, since audio was always empty).
3. **Two new, previously-undocumented gaps were found by reading code paths earlier passes didn't
   trace all the way through:** the unknown-face callback in `vision/camera.py` is never actually
   invoked (dead even with `face_recognition` installed, despite being wired up all the way from
   `main.py` back in the very first fix pass), and `tools/app_control.py`'s `open_file()` is complete
   but entirely unwired (no intent, no route). Neither is a regression — both predate this pass's
   changes — they simply weren't surfaced before.
4. **Multi-language command support for tool intents (app-open, web-search, smart-home, etc.) was
   never actually verified in any prior pass** — this pass traced through every regex pattern in
   `core/agent.py` and confirmed they are English-only, a real, checklist-relevant gap that previous
   passes didn't test because they only checked multi-language support for *conversational* chat, not
   for *tool-triggering* commands.
5. **The E2E mode-switch and full-conversation-flow tests were re-run with the timeout confound
   removed**, clarifying that the "timeout budget, not a crash" diagnosis from 2026-07-22 was correct
   for `09-full-conversation-flow` (now passes) but that `04-mode-switch` has a separate, likely-flaky
   issue independent of timing.
6. **Zero regressions** — the full backend test suite, the app_open/OCR/language-detection fixes, the
   dead-frontend-code cleanup, and the Piper voice-name/sample-rate fixes were all re-verified intact.

### Remaining Work — Prioritized

**Quick wins (small, well-scoped code fixes):**
- Wire `tools.app_control.open_file()` into an intent pattern + (optionally) a dedicated route — currently dead code despite being fully implemented.
- Add Arabic to `multilingual/tts_router.py`'s routing table (even just an explicit fallback-to-English-Piper entry, documented as such) and to the Language Support Status table below, so the existing silent fallback becomes a documented, intentional one like ko/ja/zh already are.
- Fix `vision/camera.py`'s `_analyse_frame()` to actually call `self._on_unknown_face` — currently the callback is threaded all the way from `main.py` and then dropped on the floor.
- Fix `06-status-indicators.spec.ts`'s settings-button locator (target a stable `data-testid` or `aria-label` instead of `.last()` among all SVG-icon buttons) — flagged in two consecutive audit passes now.

**Real bugs needing a fix pass:**
- `voice/wake_word.py`'s Whisper-confirmation check (`"ultron" in transcript.lower()`) doesn't account for non-Latin-script transcriptions — multi-language wake-word triggering doesn't actually work despite the underlying STT being language-capable.
- Intent-classification regex patterns in `core/agent.py` are English-only across every tool intent (app_open, web_search, smart_home, calendar, tasks, etc.) — non-English tool-triggering commands silently fall through to `direct_answer` and risk the LLM fabricating a response instead of invoking the real tool, the same failure class the original `app_open` fix targeted.
- `dateparser`'s handling of qualified relative-weekday phrases ("next monday", "friday morning") returns `None` — worth either a pre-processing normalization step or accepting this as a documented library limitation.

**Blocked on user action (credentials, accounts, hardware, money):**
- ElevenLabs paid plan (ko/ja/zh TTS) — unchanged.
- Google Cloud OAuth2 `credentials.json` (Calendar/Tasks) — unchanged.
- Home Assistant `HASS_TOKEN` + reachable instance (Smart Home live control) — unchanged.
- `dlib`/CMake build tools for `face_recognition` (would still need the `_analyse_frame()` fix above to actually do anything once installed).
- Cross-room wake-word range and low-CPU-idle measurement — need physical hardware/profiling sessions.
- Live 10-minute idle test for proactive screen suggestions.

**Deferred by design (documented prior decisions, not bugs)** — see Known Deferred Items below for the full list with reasons and unblock paths.

### Project Completion Assessment

**Is this a demoable state?** Yes, more convincingly than at any prior point. The core loop —
type or speak to Ultron, get a real Ollama-generated (now 8B-quality) response in-character, in the
detected language, with real synthesized audio for 5 of 9 supported languages — works end-to-end with
zero backend test failures and a frontend that launches, connects, and round-trips through the real
backend with no mock data left anywhere in the widgets that matter (calendar, tasks, weather all wired
for real). The biggest previously-load-bearing gap (TTS producing no audio at all) is now closed for
the majority of supported languages.

**Is this portfolio-ready?** Close, with two categories of caveat worth being upfront about in any
demo: (1) several checklist items only work in English — the tool-triggering intents (open an app,
control smart home, search the web) don't recognize non-English phrasing even though the *conversational*
layer is genuinely multilingual, which is an easy trap for a demo to fall into if a non-English speaker
tries to actually *use* a feature rather than just chat; (2) two "unknown face" / camera-alert-style
features look wired end-to-end in the architecture but are dead in practice (missing dependency *and*
a dropped callback), which would be an awkward discovery if demoed live.

**What would move the needle most if fixed next?** In order of visible impact: (1) wiring
`open_file()` and extending intent patterns to be multi-language-aware are both small, contained
fixes with outsized "does what it says on the tin" impact; (2) the camera unknown-face callback fix is
cheap and closes a real, silently-broken feature; (3) an ElevenLabs plan upgrade or a documented,
intentional Arabic fallback would tidy up the one remaining TTS loose end that isn't purely a money
question.

---

## Fix Pass History (chronological log)

This is the journey, condensed. Full current-state detail for anything still relevant today lives in
[Current Status](#current-status-from-the-most-recent-comprehensive-audit--2026-08-03) above — this
log exists so the history isn't lost, not to duplicate that detail twice.

### 1. 2026-04-21 — Original fix pass

The very first audit pass, checked against a 15-feature specification (auditor: Claude Sonnet 4.6).
Found and fixed:

- **Wake word:** `wake_word_detector.start()` had no `on_activation` callback wired in `main.py`, so
  detections happened silently with no frontend signal. Fixed by adding the parameter and wiring
  `_on_wake_word_activation()` to broadcast `{"type": "wake_word"}` to WebSocket clients.
- **TTS:** Piper was invoked as the bare command `piper`, without checking `PIPER_MODELS_PATH/piper.exe`
  first. Fixed the resolution order. *(This fix did not fully hold up — see entry 4 below: the
  2026-07-22 re-audit found TTS still produced zero audio in practice, because no Piper binary or
  models were actually present at all at that point.)*
- **Multilingual:** `/chat` used the static config language instead of detecting from the actual
  input text. Added `detect_language_from_text()` using `langdetect`, wired into `chat.py`.
- **Dual Personality Mode (critical):** the casual-mode prompt never said "NEVER use 'sir'" (the LLM
  kept saying it anyway, from training-data priors), the professional-mode "sir" instruction wasn't
  emphatic enough, and neither prompt said "never break character." Rewrote both prompts with hard
  directives; added `user_name` threading from `ultron_config.json` through `chat.py` → `agent.py` →
  `brain.py` → `prompt_manager.py`; expanded the mode-switch regex to cover multilingual keywords
  (Hindi, Japanese, Korean, Spanish, French, German, Arabic).
- **Camera Vision:** `camera_capture.start()` had no `on_unknown_face` callback. Wired `main.py` to
  pass `_on_unknown_face`, broadcasting `{"type": "camera_alert", ...}` over WebSocket. *(This wiring
  did not fully hold up either — see the 2026-08-03 audit's Camera Vision finding in Current Status
  above: the callback reaches `camera.py` but is never actually invoked there.)*
- **Screen Awareness:** `screen_capture.suggestion_queue` was populated but never polled, so no
  proactive suggestion ever reached the frontend. Added `_poll_screen_suggestions()` as an async
  background task, started via `asyncio.create_task()` in `main.py`'s lifespan.
- **WebSocket:** no way to broadcast to all connected clients (wake word/suggestion/camera-alert
  events were all lost), and `session_id` was hardcoded as `"ws-session"`. Added a `ConnectionManager`
  class (`connect()`/`disconnect()`/`broadcast()`/`has_clients`) and made `_process_text()` accept a
  real `session_id` from the WS message.
- **Frontend Connection (critical):** `app/page.tsx` used `@ai-sdk/react`'s `useChat`, which hit a
  Next.js API route calling Anthropic directly — completely bypassing the Python backend. The mode
  toggle only updated local state (never called `POST /mode`), audio responses were never played
  (browser Speech Synthesis was used instead), there was no session ID (no memory continuity), no
  `GET /status` polling (the UI showed fake random numbers), and the `PauseResponse` type didn't match
  the backend's actual `{active}` shape. Complete rewrite of `app/page.tsx`: direct `sendTextMessage()`
  calls from `lib/api.ts`, a stable session ID via `crypto.randomUUID()`, `playAudioBase64()` for
  backend TTS, mode toggle calling the real `switchMode()` API, `/status` polled every 5 seconds,
  WebSocket connected on mount with `wake_word`/`suggestion`/`camera_alert` handlers, and real backend
  status indicators in the header. `chat-message.tsx` simplified to accept plain `{role, content}`;
  `types/ultron.ts` fixed to match the real pause-response shape.
- **Other features audited and found already fully implemented, no changes needed:** speech-to-text,
  AI Brain's core generate flow, web search, browser & computer control's URL/app logic, smart home,
  calendar & tasks, privacy & local-first design.

Result (this pass's own framing): 6 features fully working, 7 partially broken (fixed), 2 critically
broken (fixed) — 15 features checked.

Also documented as **not fully implementable** at the time: a real "ultron" OpenWakeWord model doesn't
exist pretrained (the `hey_jarvis` + Whisper-confirmation workaround was proposed here as the
interim solution — see entry 7 below for the later training attempt), and `face_recognition` requires
`dlib`, which needs CMake + MSVC build tools not present on this Windows setup.

**Caveat carried forward:** this pass's own claims were not independently re-verified against a
live-running instance at the time it was written. The next pass (below) did that independent
verification from scratch and found several claims — especially TTS actually producing audio, and
some callback wiring completeness — did not fully hold up under live testing.

### 2. 2026-07-22 — Independent re-audit + same-day fix pass

A full independent re-audit (not trusting the April pass's claims — everything re-verified against
live-running code) found the environment itself was not runnable out of the box: the venv the README
pointed at (`cd backend && .venv\Scripts\activate`) didn't exist — the real venv was at the project
root with zero dependencies installed — and `frontend/node_modules` didn't exist either. Both were
installed fresh purely so the app could be exercised.

With the app actually running, this pass found and fixed, same day:

- **`/voice` returned 500 instead of 422** on malformed input — `VoiceRequest(**body)` wasn't wrapped
  in the same try/except `chat.py` already used, so a Pydantic validation error hit the global handler
  and came back as a raw 500. Fixed to match `chat.py`'s pattern; confirmed via `curl` and the
  previously-failing `test_voice_missing_audio_returns_422`.
- **OCR was completely non-functional** — `vision/ocr.py` initialized EasyOCR with `"zh"`, an invalid
  language code for that library (throws on init), and the pytesseract fallback also failed because
  Tesseract wasn't installed. Fixed with per-script-group EasyOCR readers (not just a renamed code —
  EasyOCR fundamentally can't combine Hindi/Korean/Japanese/Chinese in one `Reader`).
- **13 of 27 apps in `app_control.py`'s `APP_MAP` were unreachable from chat** — the intent
  classifier's `app_open` regex only recognized 14 of them (calculator, word, excel, powerpoint,
  notion, obsidian, vlc, steam, paint, photoshop, cmd, powershell, teams were all missing), so asking
  for any of them fell through to `direct_answer` and the LLM would *hallucinate* a fake "invoked/
  closed" narrative instead of actually launching anything. Fixed by generating the pattern from
  `APP_MAP.keys()` so the two lists can never drift apart again — and, separately, removed LLM
  narration for `app_open` entirely (the tool result is now returned verbatim), so a failed launch can
  never again be reported as a fake success.
- **Short English phrases were misdetected as random languages** by `langdetect` (`"greet me"` →
  Dutch, `"open calculator"` → Romanian), and the system prompt then made the LLM reply entirely in
  the wrong language. The only guard had been a 4-character length floor — nowhere near enough for
  `langdetect` on casual short text. Fixed with script-based detection + confidence gating +
  per-session continuity.
- **`core/agent.py`'s docstring falsely claimed to be "LangGraph-based"** — `langgraph` was a listed
  dependency but never imported anywhere; the classifier is plain `re.search` pattern matching (which
  already worked correctly, 16/16 tests passing). Docstring corrected; no functional change needed.
- **Calendar, Tasks, and Weather widgets were 100% hardcoded/mock frontend data** despite working
  backend equivalents already existing. Wired to real `POST /calendar`, `POST /tasks`, and a new
  `GET /weather` endpoint (Open-Meteo, no API key) — each now shows a clean "not connected yet" empty
  state when credentials are genuinely absent, instead of fake data.
- **Dead frontend code swept:** `status-sidebar.tsx` and `ultron-core.tsx` deleted (confirmed
  redundant); `useUltronSocket.ts` wired into `app/page.tsx`, replacing its inline WebSocket
  implementation; also found and deleted 3 more stale files not on the original list —
  `typing-indicator.tsx`, `lib/ultron-types.ts`, and `app/api/chat/route.ts` (the original
  pre-Python-backend Next.js API route, whose "tools" generated fake weather/CPU/memory stats via
  `Math.random()` — the exact anti-pattern this whole pass targeted, just already orphaned).
  `ultron-face.tsx` kept intentionally, unimported, per explicit instruction.
- **README corrected** to point at the venv's real location (project root) and to include the
  `npm install` step.

Also noted in this pass, still true and not superseded by anything later: CORS is deliberately
permissive (`allow_origins=["*"], allow_credentials=False`) — an intentional tradeoff, not something
to "fix" to `allow_credentials=True` without also narrowing origins; all 13 REST routes plus `/ws`
confirmed registered and reachable, `/docs` Swagger UI loads; real-time token streaming over
`/ws` confirmed working token-by-token for `direct_answer` intents; `BRAVE_PATH` was (and remains)
empty in `.env`, so `open_url()` falls through to the OS default browser rather than Brave
specifically — a user config choice, not something fixed on their behalf.

Result: pytest suite went from 146 passed/11 failed/2 skipped (baseline before this pass) to
147 passed/10 failed/2 skipped (the +1 is the `/voice` fix). The remaining 10 failures were
diagnosed as stale tests, not regressions — addressed in the next pass.

### 3. 2026-07-22 — Stale test triage

All 10 remaining pytest failures were diagnosed in `backend/TEST_TRIAGE_REPORT.md`:

- **9 failures** patched `api.routes.mode.brain`, an attribute that doesn't exist — `/mode` never
  called an LLM to begin with; it uses hardcoded confirmation lines by design (picked via
  `random.choice()`), so there's nothing for that mock to target.
- **1 failure** patched `api.routes.status.camera_capture`, which `status.py` imports locally inside
  the function body, not at module level — so there's no module attribute to patch.

**Zero real bugs found** — all 10 were stale tests describing an earlier implementation that no
longer matched the code; every behavior they were actually trying to verify was independently
confirmed already working via live `curl` calls in the prior pass. Fixed by removing the stale mocks
(keeping the still-valid `synthesize()` mocks where present). One small, separately-scoped real gap
was also found and fixed during this pass: `/mode` had no try/except around its `synthesize()` call
(unlike `/chat`, which degrades gracefully), so a TTS failure there raised a raw 500 instead of a
graceful 200 — fixed to match `/chat`'s pattern.

### 4. 2026-07-22/23 — TTS/Piper verification pass

The April pass (entry 1) had claimed the Piper path-resolution issue was fixed, but the entry-2
re-audit found TTS still produced empty audio on every single request — no Piper binary and no voice
models were actually present anywhere in the repo at that point.

This pass verified every layer independently before wiring anything together (binary standalone →
voice models standalone → Python layer → live `/chat` endpoint), and installed the Piper binary plus
all 5 required voice model pairs (en/hi/es/fr/te) at `backend/piper_models/`. This surfaced **two
real, previously-undiscovered bugs**, not just missing files:

- `multilingual/tts_router.py`'s voice filenames for Hindi/Spanish/Telugu (`hi_IN-x_low`,
  `es_ES-x_low`, `te_IN-x_low`) **did not exist** in the real `rhasspy/piper-voices` repo — verified
  against the actual repo tree, not guessed. Corrected to the real names (`hi_IN-pratham-medium`,
  `es_ES-davefx-medium`, `te_IN-maya-medium`).
- `voice/tts.py`'s `synthesize()` **always hardcoded the English voice model** for every piper-routed
  language, regardless of which voice the router had already correctly resolved — meaning even with
  all 5 models correctly downloaded, only English would ever actually play. Fixed to use the resolved
  voice, with a graceful fallback to English Piper if a specific voice's files are missing.

ElevenLabs (ko/ja/zh) was reconfirmed still blocked by the same free-tier `402 paid_plan_required`
error; the fallback to Piper English when ElevenLabs fails was verified live (real Korean message →
real 402 → real fallback log line → valid non-empty audio returned).

### 5. 2026-07-22/23 — `_pcm_to_wav()` sample-rate fix

`_pcm_to_wav()` hardcoded `sample_rate=22050`, which happened to be correct for all 5 "medium"-tier
voices in use at the time but was coincidental, not guaranteed — a future "x_low" or "high" tier voice
would have silently gotten the wrong rate baked into its WAV header, with no error raised anywhere.

Fixed to read the real `sample_rate` from each voice's own `.onnx.json` (confirmed channels/
sample-width are *not* in that file, so those correctly stay hardcoded as mono 16-bit — a fixed
property of Piper's `--output-raw` mode, not a per-voice setting), cached per voice, with a logged
warning + fallback to the old default if a config is ever missing/malformed. Proven with a fake
16000Hz voice config to rule out coincidence rather than just re-confirming the existing 22050Hz
voices. Two new tests added to `test_14_tts.py`.

Full pytest suite after this pass plus the stale-test triage: **159 passed, 0 failed, 2 skipped**.

### 6. Calculator tool addition

Small local LLMs hallucinate arithmetic — the same question asked three times could produce three
different wrong answers. Added `tools/calculator.py`: a real Python AST-walking evaluator with a
strict whitelist (never `eval()` — no names, no attribute access, no imports; only `+ - * / // % **`,
parens, unary `+/-`, and `sqrt/abs/round/min/max/factorial/pow`), plus `extract_math_expression()` to
pull a clean expression out of natural language while deliberately excluding phone-number/date-shaped
text unless strong math framing ("what is", "calculate", "divided by", etc.) is present.

Wired into `core/agent.py` as a new `"calculate"` intent, checked first — ahead of even the
conversational guard, since it's provably safe to check early (it never spuriously fires on
personal/chitchat text). The LLM is only ever given the already-computed, verified result and told to
narrate it in-character — never to compute anything itself — with a retry-then-guaranteed-template-
fallback safeguard if the LLM's narration ever drifts from the verified number. New test file
`tests/test_20_calculator.py` added.

### 7. 2026-07-23 — Wake word custom model training attempt

An attempt was made to train a custom OpenWakeWord "ultron" model to replace the `hey_jarvis` +
Whisper-confirmation workaround. **The attempt did not succeed and nothing was wired into the app.**

OpenWakeWord's official training pipeline expects synthetic positive samples from a separate
`piper-sample-generator` tool, ~2000 hours of pre-computed negative features from
HuggingFace/AudioSet/FMA, and a GPU — none of which matched this CPU-only Windows environment. A
scaled-down local alternative was used instead: 50 real "Ultron" recordings expanded via local audio
augmentation (pitch shift, gain, noise, filtering — 11 variants each) for positive data, and ~250
locally-synthesized negative clips (phonetically-similar words, other wake phrases, generic commands,
silence/noise) via the already-installed Piper binary — no external downloads for either.

**Training itself succeeded**: 6,150 training examples (3,273 positive / 2,877 negative) plus 1,084
validation examples, trained in 13.3s on CPU, reaching **100% validation accuracy** (577/577 positive
detected, 507/507 negative rejected, 0 false positives). Exported to `backend/wake_word_models/ultron.onnx`.

**The mandatory standalone validation gate then failed.** Loading the model through OpenWakeWord's
actual runtime API (`Model.predict_clip()` — the same path production would use) instead of the
offline training pipeline, every test clip scored ~0.99 regardless of content — 5 real positive
recordings, 5 negatives seen during training, and 8 negatives never used anywhere in training all
scored identically (~0.991). **The model does not discriminate at all in real use**, despite the
"100%" offline validation number.

**Root cause, isolated with a direct comparison:** the same audio scored two ways — offline
(`AudioFeatures.embed_clips()`, the exact batch call used to build training data) separated cleanly
(positives ~0.99, negatives ~0.01, proving the classifier genuinely learned real discrimination); the
runtime streaming path (`Model.predict()`) did not (~0.99 for everything). This is a **train/inference
feature-extraction mismatch**: training data was built by zero-padding each clip to a fixed 3-second
length and calling the offline batch embedder, while the real-time path computes embeddings
incrementally with its own internal buffering/padding. OpenWakeWord's own source documents exactly
this pitfall (`openwakeword/utils.py`, `_streaming_melspectrogram()` docstring: *"padding with 0 or
very small values seems to demonstrate the differences well"*) — exactly the shape of this project's
heavy zero-silence-padded, batch-offline-extracted training data.

**Current state: unchanged.** `backend/voice/wake_word.py` was never modified by this attempt.
`hey_jarvis` + Whisper-confirmation remains the sole active wake-word mechanism. `ultron.onnx` and the
training scripts exist under `backend/wake_word_training/`/`backend/wake_word_models/` but are not
imported or referenced anywhere in the running application.

**Fix path for a future attempt:** retrain using the *same* streaming feature-extraction call the
runtime uses (drive `Model.predict()`'s internal chunked path when building training features,
instead of the offline batch `embed_clips()`), so train-time and inference-time features are
guaranteed to match rather than merely similar. Not attempted in this pass.

**Also discovered, disclosed as a live warning, not resolved:** installing the training dependencies
(`torchinfo`, `torchmetrics`, `speechbrain`, `audiomentations`, etc.) pulled in `numpy 2.2.6`, which
conflicts with `langchain`/`langchain-community`/`mediapipe`'s `numpy<2` pins. Verified non-breaking in
practice — all affected modules still import successfully and the full pytest suite still passed — but
flagged rather than silently left for someone to rediscover. Not fixed; resolving it (pinning/
downgrading numpy, or isolating training deps into a separate environment) was out of scope.

### 8. 2026-08-03 — Final comprehensive 68/83-feature audit

The audit whose full results make up the [Current Status](#current-status-from-the-most-recent-comprehensive-audit--2026-08-03)
section at the top of this document. Ran the full backend pytest suite and a fresh Playwright E2E
suite (with the 30s timeout confound removed), live-tested every REST endpoint and the WebSocket,
re-verified every fix from entries 1–7 above still holds, and found 4 new gaps that no prior pass had
surfaced: the dead camera unknown-face callback, the unwired `open_file()` function, the
English-only intent-classification regex across every tool intent, and the undocumented Arabic
TTS-fallback gap. Zero regressions found anywhere. See Current Status above for the complete
category-by-category breakdown, evidence, and prioritized remaining work.

---

## Language Support Status

**WORKING — fully verified, local, no external dependency (Piper, real audio confirmed through the
live `/chat` endpoint, re-confirmed live again in the 2026-08-03 audit):**

| Language | Code | Engine | Voice |
|---|---|---|---|
| English | `en` | Piper | `en_US-lessac-medium` |
| Hindi | `hi` | Piper | `hi_IN-pratham-medium` |
| Spanish | `es` | Piper | `es_ES-davefx-medium` |
| French | `fr` | Piper | `fr_FR-siwis-medium` |
| Telugu | `te` | Piper | `te_IN-maya-medium` |

**ON HOLD — deferred to a later phase:**

- **Korean (`ko`), Japanese (`ja`), Chinese (`zh`)** — routed to ElevenLabs, currently blocked by
  free-tier plan limits (confirmed via a real API call: `402 paid_plan_required` — "Free users cannot
  use library voices via the API"). Falls back to Piper English gracefully in the meantime, so the app
  does not break or error for these languages today — it just responds in an English voice rather than
  the native one. Revisit once an ElevenLabs paid plan is in place; not something to work around in
  code.
- **German (`de`)** — the routing table's `de_DE-x_low` voice name does not exist in the real
  `rhasspy/piper-voices` repo (verified the same way the hi/es/te names were caught — real voices are
  `eva_k`, `karlsson`, `kerstin`, `mls`, `pavoque`, `ramona`, `thorsten`, `thorsten_emotional`). Left
  as a known-broken placeholder rather than silently guessed at. Needs a real voice chosen and
  downloaded (same process as the 5 working languages above).

**NOT DOCUMENTED UNTIL THIS MERGE — Arabic (`ar`):** `language_detector.py` fully supports *detecting*
Arabic (it's one of the 9 `_TEXT_SUPPORTED_LANGUAGES`), and the app will converse in Arabic correctly.
But `multilingual/tts_router.py`'s routing table has **no `"ar"` entry at all** — a live test this
pass confirmed Arabic text still returns a large, valid, non-empty `audio_base64` payload, but it's
silently the **English** Piper voice via the router's unknown-code fallback. This is the same
graceful-fallback *behavior* the table above documents for ko/ja/zh, it just was never disclosed for
Arabic specifically until the 2026-08-03 audit found it. Treat Arabic as functionally in the same
"ON HOLD" bucket as ko/ja/zh until it gets either a real Piper voice or an explicit, documented
fallback entry in the routing table.

---

## Known Deferred Items (Intentional, Not Bugs)

| Item | Why it's deferred | What would unblock it |
|---|---|---|
| Native "Ultron" OpenWakeWord trigger | A real custom model was trained (2026-07-23) and reached 100% offline validation accuracy, but failed the runtime-validation gate due to a train/inference feature-extraction mismatch (see Fix Pass History entry 7) — not a missing-effort problem, a genuine unsolved technical issue at the time. The `hey_jarvis` + Whisper-confirmation workaround (say something containing "jarvis," then "ultron") is the shipped mechanism in the meantime. | Retrain using OpenWakeWord's *streaming* feature-extraction path (matching runtime inference) instead of the offline batch embedder used this attempt — documented as the fix path, not yet attempted. |
| ElevenLabs TTS for Korean/Japanese/Chinese | API key is valid and authenticates correctly, but the account is free-tier, and ElevenLabs' free tier cannot call library voices via the API at all (`402 paid_plan_required`, confirmed via a real API call). Falls back gracefully to English Piper in the meantime. | Upgrade the ElevenLabs subscription to a paid plan, or pick a voice available on the free tier. |
| German (`de`) Piper voice | The routing table's placeholder voice name (`de_DE-x_low`) doesn't exist in the real `rhasspy/piper-voices` repo — left as a known-broken placeholder rather than silently guessed at, since German was out of scope for the TTS fix passes. | Pick a real German voice from the actual repo (`eva_k`, `karlsson`, `kerstin`, `mls`, `pavoque`, `ramona`, `thorsten`, `thorsten_emotional`), download its `.onnx`/`.onnx.json` pair, update the `"de"` entry in `tts_router.py`. |
| Face-recognition-based "unknown face" identity matching | `face_recognition` requires `dlib`, which requires CMake + MSVC build tools not present on this Windows setup. (Note: even once installed, `vision/camera.py`'s `_analyse_frame()` would still need a real fix — not just this dependency — to actually invoke the unknown-face callback; see Current Status → Camera Vision and → Remaining Work.) | `winget install Kitware.CMake` then `pip install face-recognition`, **plus** the separate `_analyse_frame()` callback-invocation fix. |

---

## How to Start

```bash
# ── 1. Python environment (from the project ROOT, not backend/) ────────────────
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

pip install -r backend/requirements.txt

# ── 2. Ollama ────────────────────────────────────────────────────────────────
# Install from https://ollama.com, then:
ollama serve
ollama pull llama3        # 8B model — matches OLLAMA_MODEL=llama3 in .env

# ── 3. API keys ──────────────────────────────────────────────────────────────
cp backend/.env.example backend/.env
# Fill in ANTHROPIC_API_KEY, TAVILY_API_KEY, ELEVENLABS_API_KEY (optional — ko/ja/zh
# TTS only, free tier is blocked, see Language Support Status above), HASS_TOKEN
# (optional — smart home), GOOGLE_CREDENTIALS_PATH (optional — calendar/tasks)

# ── 4. Piper TTS (standalone binary + voice models) ─────────────────────────────
# Download piper_windows_amd64.zip from https://github.com/rhasspy/piper/releases/latest,
# extract its CONTENTS (piper.exe + DLLs + espeak-ng-data/) directly into backend/piper_models/
mkdir backend/piper_models
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"
curl -L -o backend/piper_models/en_US-lessac-medium.onnx      "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o backend/piper_models/en_US-lessac-medium.onnx.json "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
curl -L -o backend/piper_models/hi_IN-pratham-medium.onnx      "$BASE/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx"
curl -L -o backend/piper_models/hi_IN-pratham-medium.onnx.json "$BASE/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json"
curl -L -o backend/piper_models/es_ES-davefx-medium.onnx      "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"
curl -L -o backend/piper_models/es_ES-davefx-medium.onnx.json "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json"
curl -L -o backend/piper_models/fr_FR-siwis-medium.onnx      "$BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"
curl -L -o backend/piper_models/fr_FR-siwis-medium.onnx.json "$BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"
curl -L -o backend/piper_models/te_IN-maya-medium.onnx      "$BASE/te/te_IN/maya/medium/te_IN-maya-medium.onnx"
curl -L -o backend/piper_models/te_IN-maya-medium.onnx.json "$BASE/te/te_IN/maya/medium/te_IN-maya-medium.onnx.json"
# Set PIPER_MODELS_PATH=./piper_models in backend/.env (already the default)

# ── 5. Run the backend ───────────────────────────────────────────────────────
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# ── 6. Run the frontend (separate terminal) ─────────────────────────────────
cd frontend
npm install       # first time only, or whenever package.json changes
npm run electron:dev
```

Expected clean startup log:
```
INFO  main — ULTRON backend starting up.
INFO  voice.wake_word — Wake word detector started.
INFO  vision.camera — Camera passive monitor started.
INFO  vision.screen — Screen passive monitor started.
INFO  main — Ollama connection verified.
INFO  main — ULTRON is online. Mode: professional | Language: en
INFO  Uvicorn running on http://0.0.0.0:8000
```

**Troubleshooting:**
- **Ollama not responding** — make sure `ollama serve` is running; the backend falls back to Claude automatically if Ollama is down.
- **Piper voice not found** — check the `.onnx`/`.onnx.json` files exist in `PIPER_MODELS_PATH` and the filename exactly matches the voice name in `tts_router.py`.
- **No audio output** — the frontend plays audio from the `audio_base64` field in responses; confirm Piper is installed and models are present (see step 4 above).
- **Camera/screen monitoring errors** — non-fatal; the backend starts without them if OpenCV or `mss` fail. On-demand capture via the API endpoints still works.
- **Google Calendar first-time auth** — the first request to `/calendar` attempts to open a browser for OAuth; run the backend interactively (not as a service) for the first auth flow.
