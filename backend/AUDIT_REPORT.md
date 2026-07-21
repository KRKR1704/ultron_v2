# ULTRON Backend — Full Audit Report

**Date:** 2026-04-21  
**Auditor:** Claude Sonnet 4.6

---

## Audit Summary

Every feature was audited against the specification. 15 features checked.
Results: 6 fully working, 7 partially broken, 2 critically broken (fixed).

---

## Feature-by-Feature Results

### Feature 1 — Wake Word Detection
**Status before:** ⚠️ Partial  
**Issue:** `wake_word_detector.start()` was called without an `on_activation` callback in `main.py`, so wake word detection ran silently with no frontend signal.  
**Fix:**
- `voice/wake_word.py` — added `on_activation` parameter to `start()` 
- `main.py` — wired `_on_wake_word_activation()` callback that broadcasts `{"type": "wake_word"}` to all connected WebSocket clients via `ConnectionManager`

---

### Feature 2 — Speech To Text (STT)
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 3 — Text To Speech (TTS)
**Status before:** ⚠️ Partial  
**Issue:** Piper was called as the bare command `piper` — didn't check `PIPER_MODELS_PATH/piper.exe` first.  
**Fix:** `voice/tts.py` — now tries candidates in order: `PIPER_MODELS_PATH/piper.exe`, `piper.exe` on PATH, `piper` on PATH.

---

### Feature 4 — Multilingual Engine
**Status before:** ⚠️ Partial  
**Issue:** The `/chat` endpoint used `app_state["config"]["language"]` (always "en") instead of detecting the language from the actual input text. Voice (STT) route was correct; text chat was not.  
**Fix:**
- `multilingual/language_detector.py` — added `detect_language_from_text(text)` using `langdetect`
- `api/routes/chat.py` — calls `detect_language_from_text()` on every text chat request
- `requirements.txt` — added `langdetect==1.0.9`

---

### Feature 5 — Dual Personality Mode (CRITICAL)
**Status before:** ❌ Broken  
**Issues:**

**Problem A — System prompt not actually enforcing mode:**
- `_PROFESSIONAL` used `"refer to the user as 'sir'"` — no emphasis, LLM would drift
- `_CASUAL` did NOT say `"NEVER use 'sir'"` — LLM kept saying sir in casual mode because training data associates Ultron with "sir"
- Both modes missing `"Never break character."`

**Problem B — Mode switch confirmation not using new mode:**  
The confirmation for short mode-switch messages was a hardcoded string (acceptable). For longer messages, `run_agent()` was called with the already-updated mode. This was working correctly.

**Problem C — Session history retaining old tone:**  
`memory.clear_session()` was already called on mode switch. This was working correctly.

**Root cause:** Prompts were insufficiently directive. LLMs use training data priors heavily. Without an explicit `"NEVER use 'sir'"` instruction, casual mode still said sir. 

**Fix:** `core/prompt_manager.py`
```python
# Professional:
"You ALWAYS refer to the user as 'sir' — every single response, no exceptions."
"Never break character. Never be warm, never be casual, never drop 'sir'."

# Casual:
"NEVER use the word 'sir' — not once, not ever, in any response."
"Never break character."
```

Additional fixes:
- `build_system_prompt()` now accepts `user_name` parameter for casual mode personalisation
- `user_name` from `ultron_config.json` propagated through: `chat.py` → `agent.py` → `brain.py` → `prompt_manager.py`
- Mode switch patterns in `chat.py` expanded to cover multilingual keywords (Hindi, Japanese, Korean, Spanish, French, German, Arabic)

---

### Feature 6 — AI Brain
**Status before:** ✅ Fully implemented  
**Minor fix:** `brain.generate()` now accepts and passes `user_name` to `build_system_prompt()`.

---

### Feature 7 — Web Search
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 8 — Browser & Computer Control
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 9 — Camera Vision
**Status before:** ⚠️ Partial  
**Issue:** `camera_capture.start()` was called without the `on_unknown_face` callback.  
**Fix:** `main.py` — passes `_on_unknown_face` callback that broadcasts `{"type": "camera_alert", "message": "..."}` to all WS clients.

---

### Feature 10 — Screen Awareness
**Status before:** ⚠️ Partial  
**Issue:** `screen_capture.suggestion_queue` was populated correctly but never polled — no proactive suggestions reached the frontend.  
**Fix:**
- `api/websocket.py` — added `_poll_screen_suggestions()` async background task
- `main.py` — starts this task with `asyncio.create_task()` during lifespan

---

### Feature 11 — Smart Home
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 12 — Calendar & Tasks
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 13 — WebSocket Real-Time Streaming
**Status before:** ⚠️ Partial  
**Issues:**
- No way to broadcast to all connected clients (wake word, suggestions, camera alerts were all lost)
- `session_id` was hardcoded as `"ws-session"` — text messages couldn't specify session

**Fix:** `api/websocket.py`
- Added `ConnectionManager` class with `connect()`, `disconnect()`, `broadcast()`, `has_clients`
- Module-level `manager` singleton imported by `main.py` for callback wiring
- `_process_text()` now accepts a `session_id` parameter from the WS JSON message
- Added `_poll_screen_suggestions()` background task

---

### Feature 14 — Privacy & Local First
**Status before:** ✅ Fully implemented  
**No changes needed.**

---

### Feature 15 — Frontend Connection
**Status before:** ❌ Broken  
**Issues:**
1. `app/page.tsx` used `useChat` from `@ai-sdk/react` which called `/api/chat` (Next.js API route with Anthropic SDK) — completely bypassing the Python backend
2. Mode toggle button called `setPersonalityMode()` locally — never called `POST /mode`
3. Audio responses from backend were never played (used browser Speech Synthesis instead)
4. No session ID — every request had no memory continuity
5. No `GET /status` polling — UI status was fake random numbers
6. `PauseResponse` shape mismatch: frontend expected `{camera_active, screen_active}`, backend returns `{active}`
7. `ChatMessage` used AI SDK's `UIMessage` type, incompatible with simple `{role, content}`

**Fixes:**
- `app/page.tsx` — complete rewrite:
  - Replaced `useChat` with direct `sendTextMessage()` calls from `lib/api.ts`
  - Added `crypto.randomUUID()` session ID (stable per app launch via `useRef`)
  - Added `playAudioBase64()` for backend TTS playback
  - Mode toggle calls `switchMode()` API, plays confirmation audio from backend
  - `GET /status` polled every 5 seconds — syncs mode and monitoring states
  - WebSocket connected on mount, auto-reconnects, handles `wake_word`/`suggestion`/`camera_alert` events
  - Real backend status indicators in header (camera, wake word)
- `components/ultron/chat-message.tsx` — simplified to accept `{id, role, content, timestamp}`
- `types/ultron.ts` — fixed `PauseCameraResponse` and `PauseScreenResponse` to use `{active: bool}`

---

## Files Changed

### Backend
| File | Change |
|------|--------|
| `core/prompt_manager.py` | Fixed prompts; added user_name; "NEVER use 'sir'"; "Never break character" |
| `multilingual/language_detector.py` | Added `detect_language_from_text()` |
| `api/routes/chat.py` | Language detection; multilingual mode switch patterns; user_name propagation |
| `core/agent.py` | Added `user_name` parameter |
| `core/brain.py` | Added `user_name` parameter; passes to prompt_manager |
| `api/routes/mode.py` | Passes user_name to brain.generate() |
| `api/routes/voice.py` | Passes user_name from config |
| `api/websocket.py` | ConnectionManager; broadcast; proactive suggestion poller |
| `main.py` | Wake word callback; camera callback; suggestion poller task |
| `voice/wake_word.py` | `start()` accepts optional `on_activation` callback |
| `voice/tts.py` | Piper exe path resolution: PIPER_MODELS_PATH first |
| `requirements.txt` | Added `langdetect==1.0.9` |

### Frontend
| File | Change |
|------|--------|
| `app/page.tsx` | Full rewrite — uses backend API, session ID, audio playback, mode sync, status poll |
| `components/ultron/chat-message.tsx` | Simplified to accept plain `{role, content}` messages |
| `types/ultron.ts` | Fixed PauseCameraResponse and PauseScreenResponse shapes |

---

## Features Not Fully Implementable

### Wake word "ultron" / "hey ultron"
OpenWakeWord does not have a pretrained model for the word "Ultron". The workaround is to use `hey_jarvis` as the trigger keyword, then confirm via faster-whisper that the transcript contains "ultron". This provides functional wake word behaviour but requires the user to say a phrase that contains "ultron" — e.g. "hey jarvis" to trigger OWW, then Whisper confirms "ultron" in the follow-up audio.

**Proper fix:** Train a custom OWW model on "hey ultron" recordings. This requires 100+ audio samples and the OWW training toolkit. Instructions: https://github.com/dscripka/openWakeWord

### Face recognition (unknown face alerts)
`face_recognition` requires `dlib` which requires CMake + MSVC build tools on Windows Python 3.11. The camera runs without it (passive motion detection via MediaPipe), but person identification is unavailable without installing dlib.

---

## How to Start

```bash
# Terminal 1 — Backend
cd C:\aa\UltronV2\backend
.venv\Scripts\activate
pip install langdetect   # new dependency
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — Frontend
cd C:\aa\UltronV2\frontend
npm run electron:dev
```
