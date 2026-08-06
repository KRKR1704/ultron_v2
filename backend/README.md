# ULTRON Backend

FastAPI backend for the ULTRON personal AI assistant desktop app.

- **Backend:** http://localhost:8000
- **Frontend:** http://localhost:3000 (Electron + Next.js)
- **WebSocket:** ws://localhost:8000/ws

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed locally
- (Optional) Piper TTS voice models
- API keys for the services you want to use

---

## 1. Python 3.11 Setup

```bash
# Windows (winget)
winget install Python.Python.3.11

# Mac
brew install python@3.11

# Verify
python3.11 --version
```

---

## 2. Create virtual environment & install dependencies

The virtual environment lives at the **project root** (one level above
`backend/`), not inside `backend/` — run these commands from the repo root
(the folder that contains both `backend/` and `frontend/`), not from inside
`backend/` itself.

```bash
# From the project root (the parent of backend/ and frontend/)

# Create venv
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install all backend dependencies
pip install -r backend/requirements.txt
```

> **Note for Windows users:** `face-recognition` requires `cmake` and Visual Studio
> build tools. Install with:
> `winget install Kitware.CMake` then `pip install face-recognition`

---

## 3. Install and start Ollama

```bash
# Download from https://ollama.com and install, then:
ollama serve

# Pull the llama3 model (one-time ~4 GB download)
ollama pull llama3

# Verify it works
ollama run llama3 "Say hello"
```

---

## 4. Configure API keys

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and fill in your keys:
# - ANTHROPIC_API_KEY  → https://console.anthropic.com
# - TAVILY_API_KEY     → https://tavily.com
# - ELEVENLABS_API_KEY → https://elevenlabs.io (Korean/Japanese/Chinese TTS —
#   note: ElevenLabs's free tier cannot use library voices via the API at
#   all (402 paid_plan_required), so ko/ja/zh TTS falls back to English
#   Piper until a paid plan is added; see "Language Support Status" below)
# - HASS_TOKEN         → Home Assistant → Profile → Long-lived access tokens
```

---

## 5. Install Piper TTS (standalone binary)

The `piper-tts` Python package does not support Python 3.11+ on Windows.
Instead, install the **standalone piper executable** and put it on your PATH
(or in `PIPER_MODELS_PATH` — the backend checks there first, so keeping
`piper.exe` next to the voice models below is the simplest option).

### Windows

1. Download the latest `piper_windows_amd64.zip` from:
   https://github.com/rhasspy/piper/releases/latest

2. Extract it — you'll get a `piper/` folder containing `piper.exe` plus its
   required DLLs and an `espeak-ng-data/` folder. Move the *contents* of
   that folder (not the folder itself) directly into `backend/piper_models/`
   so `piper.exe` sits next to the voice model files below.

3. Verify: `cd backend/piper_models && .\piper.exe --help` should print
   real usage info — if you get a "not recognized" or missing-DLL error,
   the DLLs/`espeak-ng-data/` didn't get copied alongside `piper.exe`.

### Mac / Linux

```bash
# Mac (Homebrew)
brew install piper-tts

# Linux — download from releases page, extract, add to PATH
```

### Download voice models

The filenames below are **verified against the actual
`rhasspy/piper-voices` repository tree** — earlier versions of this
project's language routing table guessed at generic `{lang}-x_low` names
for Hindi/Spanish/Telugu that turned out not to exist there at all. Use the
exact names below (all "medium" quality, ~60MB each).

```bash
cd backend
mkdir piper_models

BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main"

# English (required — used as the fallback for every other language too)
curl -L -o piper_models/en_US-lessac-medium.onnx      "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o piper_models/en_US-lessac-medium.onnx.json "$BASE/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

# Hindi
curl -L -o piper_models/hi_IN-pratham-medium.onnx      "$BASE/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx"
curl -L -o piper_models/hi_IN-pratham-medium.onnx.json "$BASE/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json"

# Spanish
curl -L -o piper_models/es_ES-davefx-medium.onnx      "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx"
curl -L -o piper_models/es_ES-davefx-medium.onnx.json "$BASE/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json"

# French
curl -L -o piper_models/fr_FR-siwis-medium.onnx      "$BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx"
curl -L -o piper_models/fr_FR-siwis-medium.onnx.json "$BASE/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json"

# Telugu
curl -L -o piper_models/te_IN-maya-medium.onnx      "$BASE/te/te_IN/maya/medium/te_IN-maya-medium.onnx"
curl -L -o piper_models/te_IN-maya-medium.onnx.json "$BASE/te/te_IN/maya/medium/te_IN-maya-medium.onnx.json"
```

Browse all available voices at:
https://huggingface.co/rhasspy/piper-voices/tree/main

Set `PIPER_MODELS_PATH=./piper_models` in your `.env` file.

---

## Language Support Status

**WORKING** — fully verified through the live `/chat` endpoint, local, no external dependency or API key required:

| Language | Code | Engine | Voice |
|---|---|---|---|
| English | `en` | Piper | `en_US-lessac-medium` |
| Hindi | `hi` | Piper | `hi_IN-pratham-medium` |
| Spanish | `es` | Piper | `es_ES-davefx-medium` |
| French | `fr` | Piper | `fr_FR-siwis-medium` |
| Telugu | `te` | Piper | `te_IN-maya-medium` |

**ON HOLD** — deferred to a later phase, not currently working:

- **Korean (`ko`), Japanese (`ja`), Chinese (`zh`)** — routed to ElevenLabs, blocked by ElevenLabs's free-tier plan (library voices require a paid plan — `402 paid_plan_required`). The app does not break or error for these languages: it gracefully falls back to Piper English, so you'll hear a response, just not in the requested language's voice. Revisit once an ElevenLabs paid plan is available.
- **German (`de`)** — the routing table points at a voice filename (`de_DE-x_low`) that doesn't exist in the real `rhasspy/piper-voices` repo. No German voice has been downloaded/verified yet. To add it: pick a real voice from `https://huggingface.co/rhasspy/piper-voices/tree/main/de/de_DE` (e.g. `thorsten`, `eva_k`, `kerstin`), download its `.onnx`/`.onnx.json` pair the same way as above, and update the `"de"` entry in `multilingual/tts_router.py`.

---

## 6. Google Calendar OAuth2 setup

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Calendar API** and **Tasks API**
3. Create OAuth2 credentials → Download as `credentials.json`
4. Place `credentials.json` in the `backend/` folder
5. Set `GOOGLE_CREDENTIALS_PATH=./credentials.json` in `.env`
6. On first run, a browser window will open to authorise access

---

## 7. Home Assistant token

1. In Home Assistant, go to **Profile → Security → Long-lived access tokens**
2. Create a new token and copy it
3. Set `HASS_TOKEN=<your-token>` and `HASS_URL=http://homeassistant.local:8123` in `.env`

---

## 8. Run the backend

```bash
# Activate the venv from the project root (see step 2), then:
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
```
INFO  ULTRON backend starting up.
INFO  Ollama connection verified.
INFO  ULTRON is online. Mode: professional | Language: en
INFO  Uvicorn running on http://0.0.0.0:8000
```

---

## 9. Run the frontend

In a separate terminal from the `frontend/` directory:

```bash
cd ../frontend

# First time only (or whenever package.json changes):
npm install

npm run electron:dev
```

The Electron window will open pointing to http://localhost:3000.
The frontend connects to the backend at http://localhost:8000.

---

## 10. How they connect

```
┌─────────────────────────────┐        ┌────────────────────────────────┐
│   Electron Desktop App      │        │    FastAPI Backend              │
│   Next.js on :3000          │◄──────►│    uvicorn on :8000            │
│                             │  HTTP  │                                │
│   POST /chat                │        │   Ollama (llama3) primary      │
│   POST /voice               │        │   Claude claude-opus-4-6 fallback       │
│   POST /vision/camera       │        │                                │
│   POST /vision/screen       │        │   Voice: faster-whisper + piper│
│   GET  /status (5s poll)    │        │   Vision: OpenCV + Claude      │
│   WS   /ws (streaming)      │◄──────►│   Tools: Tavily, HA, Calendar  │
└─────────────────────────────┘  WS    └────────────────────────────────┘
```

---

## 11. Memory vault (`backend/vault/`)

Ultron keeps a persistent, human-readable memory vault at `backend/vault/`,
written as real Obsidian-compatible markdown — genuinely nice to open in
Obsidian, not just a log dump. It's gitignored and **contains real personal
conversation data** — never commit it, never share it.

```
backend/vault/
  raw/       one markdown file per day (raw/2026-08-06.md) — every chat/voice
             turn, with timestamp, session ID, detected language, active
             mode, and any tool/intent triggered
  wiki/      one note per notable entity/topic (wiki/OweWise.md), cross-linked
             with raw/ notes via real [[wikilinks]]
  outputs/   reserved for generated content (search summaries, calendar
             digests, ...) — wired up incrementally, empty today
```

This is separate from (and durable across restarts, unlike) `core/memory.py`'s
in-session conversation history — see `core/vault.py` for the implementation.
Cross-session recall is automatic: when a session is new or has little
context, Ultron does a cheap, scoped lookup against `wiki/` note titles and
injects any relevant prior context into the prompt.

To open the vault in Obsidian: `File → Open folder as vault →
backend/vault/`.

## 12. Skills system (`backend/skills/`)

Every tool-triggering intent (web search, opening apps/files, smart home,
calendar, tasks, camera/screen analysis, the calculator) plus mode-switch
detection is defined declaratively in a `*.SKILL.md` file under
`backend/skills/`, not hardcoded in `core/agent.py`. `core/agent.py` loads
all of them at startup and builds its classifier from that data — this is
still plain regex pattern matching under the hood (not "real" LangGraph, see
`core/agent.py`'s module docstring), just data-driven instead of hardcoded.

**To add a new skill:** create a new `backend/skills/<name>.SKILL.md` file
with a unique `priority`, trigger patterns, and a `handler` reference to a
Python function — no changes to `core/agent.py` needed. See
`backend/skills/README.md` for the full format reference and a
fully-documented example (`web_search.SKILL.md`).

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Text message → AI response |
| POST | `/voice` | Audio (base64 or multipart) → transcript + response |
| POST | `/vision/camera` | Webcam frame analysis |
| POST | `/vision/screen` | Screenshot analysis |
| POST | `/mode` | Switch professional/casual mode |
| POST | `/smarthome` | Home Assistant commands |
| POST | `/calendar` | Google Calendar actions |
| POST | `/tasks` | Google Tasks actions |
| GET | `/status` | System status (polled every 5s by frontend) |
| POST | `/pause/camera` | Toggle camera monitoring |
| POST | `/pause/screen` | Toggle screen monitoring |
| WS | `/ws` | Real-time audio streaming |

---

## Troubleshooting

**Ollama not responding:** Make sure `ollama serve` is running. The backend falls back to Claude automatically if Ollama is down.

**Piper voice not found:** Check that the `.onnx` and `.onnx.json` files exist in `PIPER_MODELS_PATH`. The filename must exactly match the voice name in `tts_router.py`.

**No audio output:** The frontend plays audio from the `audio_base64` field in responses. Check that piper is installed (`pip install piper-tts`) and the model files are present.

**Camera/screen monitoring errors:** These are non-fatal. The backend starts without them if OpenCV or mss fail. You can still use on-demand capture via the API endpoints.

**Google Calendar first-time auth:** The first request to `/calendar` will attempt to open a browser for OAuth. Run the backend interactively (not as a service) for the first auth flow.
