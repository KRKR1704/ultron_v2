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

```bash
cd backend

# Create venv
python -m venv .venv

# Activate
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install all dependencies
pip install -r requirements.txt
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
# - ELEVENLABS_API_KEY → https://elevenlabs.io (only needed for Korean/Japanese/Chinese TTS)
# - HASS_TOKEN         → Home Assistant → Profile → Long-lived access tokens
```

---

## 5. Install Piper TTS (standalone binary)

The `piper-tts` Python package does not support Python 3.11+ on Windows.
Instead, install the **standalone piper executable** and put it on your PATH.

### Windows

1. Download the latest `piper_windows_amd64.zip` from:
   https://github.com/rhasspy/piper/releases/latest

2. Extract it — you'll get a `piper/` folder containing `piper.exe`.

3. Add the extracted folder to your PATH, **or** copy `piper.exe` into your
   `backend/` folder (it will be found automatically when the backend runs).

4. Verify: open a new terminal and run `piper --help`

### Mac / Linux

```bash
# Mac (Homebrew)
brew install piper-tts

# Linux — download from releases page, extract, add to PATH
```

### Download voice models

```bash
cd backend
mkdir piper_models

# English (required — used as fallback for all languages)
curl -L -o piper_models/en_US-lessac-medium.onnx \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
curl -L -o piper_models/en_US-lessac-medium.onnx.json \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
```

Browse all available voices at:
https://huggingface.co/rhasspy/piper-voices/tree/main

Set `PIPER_MODELS_PATH=./piper_models` in your `.env` file.

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
# From the backend/ directory with venv activated:
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
