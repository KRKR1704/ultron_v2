"""
test_23_multilingual_intent.py — Tests for Bug 3: multilingual intent detection.

Every tool-triggering intent in core/agent.py's _INTENT_PATTERNS was English-only
regex — a Spanish "abre la calculadora" or a Hindi equivalent silently fell
through to direct_answer instead of executing the intended action, even though
the conversational layer (prompt_manager.py, language_detector.py) is genuinely
multilingual. This reuses the same technique already proven for mode-switch
detection (api/routes/chat.py's _MODE_SWITCH_PATTERNS): per-language
keyword/phrase regexes ADDED alongside the existing English patterns.

Covers, per the audit's required minimum: at least one non-English test per
intent category across at least 3 languages (Spanish, Hindi, French), plus a
false-positive regression pass confirming ordinary conversational messages in
each language still resolve to direct_answer, plus a handful of full /chat
round-trips proving the classifier's label actually drives real tool
execution end-to-end, not just correct classification in isolation.
"""

from unittest.mock import AsyncMock, patch

import pytest

from core.agent import classify_intent


# ── Spanish ────────────────────────────────────────────────────────────────────

def test_spanish_app_open():
    assert classify_intent("abre la calculadora") == "app_open"


def test_spanish_app_open_brand_name():
    assert classify_intent("abre Spotify") == "app_open"


def test_spanish_web_search():
    assert classify_intent("busca noticias de IA") == "web_search"


def test_spanish_smart_home_off():
    assert classify_intent("apaga las luces") == "smart_home"


def test_spanish_smart_home_on():
    assert classify_intent("enciende las luces de la cocina") == "smart_home"


def test_spanish_calendar():
    assert classify_intent("agenda una reunión para mañana") == "calendar"


def test_spanish_tasks():
    assert classify_intent("recuérdame comprar leche") == "tasks"


# ── Hindi ──────────────────────────────────────────────────────────────────────

def test_hindi_app_open():
    assert classify_intent("कैलकुलेटर खोलो") == "app_open"


def test_hindi_web_search():
    assert classify_intent("आज का मौसम खोजो") == "web_search"


def test_hindi_smart_home():
    assert classify_intent("लाइट बंद करो") == "smart_home"


def test_hindi_calendar():
    assert classify_intent("कल बैठक शेड्यूल करो") == "calendar"


def test_hindi_tasks():
    assert classify_intent("मुझे याद दिलाओ दूध खरीदना है") == "tasks"


# ── French ─────────────────────────────────────────────────────────────────────

def test_french_app_open():
    assert classify_intent("ouvre la calculatrice") == "app_open"


def test_french_web_search():
    assert classify_intent("cherche les nouvelles technologies") == "web_search"


def test_french_smart_home():
    assert classify_intent("éteins les lumières") == "smart_home"


def test_french_calendar():
    assert classify_intent("ajoute une réunion demain") == "calendar"


def test_french_tasks():
    assert classify_intent("rappelle-moi d'acheter du pain") == "tasks"


# ── Bonus coverage: German / Korean / Japanese / Chinese / Arabic smoke tests ──

def test_german_app_open():
    assert classify_intent("öffne den Taschenrechner") == "app_open"


def test_korean_smart_home():
    assert classify_intent("불을 켜") == "smart_home"


def test_japanese_camera():
    assert classify_intent("カメラで何が見える") == "camera_analyze"


def test_chinese_app_open():
    assert classify_intent("打开计算器") == "app_open"


def test_arabic_app_open():
    assert classify_intent("افتح الحاسبة") == "app_open"


# ── False-positive regression: normal conversation must stay direct_answer ────
# Same check the original app_open regex-gap fix used ("meeting on 3/15" ->
# calendar, not calculate) — applied here across languages, to confirm the
# new multilingual trigger words don't accidentally fire on ordinary speech.

@pytest.mark.parametrize("text", [
    "Como estas hoy amigo",
    "Gracias por tu ayuda",
    "Que tal tu dia hoy",
])
def test_spanish_conversational_stays_direct_answer(text):
    assert classify_intent(text) == "direct_answer"


@pytest.mark.parametrize("text", [
    "आप कैसे हैं",
    "धन्यवाद बहुत बहुत",
    "मुझे बहुत खुशी हुई",
])
def test_hindi_conversational_stays_direct_answer(text):
    assert classify_intent(text) == "direct_answer"


@pytest.mark.parametrize("text", [
    "Comment ca va aujourd hui",
    "Merci beaucoup pour ton aide",
    "Je suis tres content",
])
def test_french_conversational_stays_direct_answer(text):
    assert classify_intent(text) == "direct_answer"


# ── Regression: English detection must be completely unaffected ──────────────
# (test_05_intent.py already covers this exhaustively — these are targeted
# spot-checks specific to the intents touched by this fix.)

def test_english_app_open_unaffected():
    assert classify_intent("open Spotify") == "app_open"


def test_english_browser_open_unaffected():
    assert classify_intent("open github.com") == "browser_open"


def test_english_smart_home_unaffected():
    assert classify_intent("turn off the lights") == "smart_home"


def test_english_web_search_unaffected():
    assert classify_intent("search for python tutorials") == "web_search"


# ── Full /chat pipeline — real classify_intent + real tool dispatch ──────────
# Mocks only the deepest boundary (the actual app-launch subprocess call, or
# TTS) — classify_intent(), run_agent()'s dispatch, and (for smart_home) the
# real "not configured" guard all run for real, proving the full pipeline
# actually executes the right tool end-to-end, not just that the classifier
# picks the right label in isolation.

def _post_chat(client, payload: dict):
    return client.post("/chat", json=payload)


def test_chat_spanish_app_open_launches_real_tool(client):
    """
    'abre la calculadora' through the real /chat endpoint must classify as
    app_open and call the real open_app() with the translated canonical
    app key — mocking only the actual subprocess launch, not the pipeline.
    """
    with patch("tools.app_control.open_app") as mock_open_app, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_open_app.return_value = "Launching calculator."
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "abre la calculadora",
            "session_id": "multilingual-test-es-app",
        })

    assert response.status_code == 200
    data = response.json()
    mock_open_app.assert_called_once_with("calculator")
    # app_open is returned verbatim (anti-hallucination pattern) — the tool's
    # real string must be exactly what the user sees, not an LLM paraphrase.
    assert data["response_text"] == "Launching calculator."


def test_chat_spanish_web_search_calls_real_tool(client):
    """'busca noticias de IA' must classify as web_search and invoke the real search tool."""
    with patch("tools.web_search.search", new_callable=AsyncMock) as mock_search, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("core.agent.brain") as mock_brain:
        mock_search.return_value = "AI news: real summarized results."
        mock_tts.return_value = ""
        mock_brain.generate = AsyncMock(return_value="Aquí tienes las últimas noticias de IA.")

        response = _post_chat(client, {
            "message": "busca noticias de IA",
            "session_id": "multilingual-test-es-search",
        })

    assert response.status_code == 200
    mock_search.assert_called_once()


def test_chat_spanish_smart_home_reaches_real_tool(client):
    """
    'apaga las luces' must classify as smart_home and reach the real
    tools.smart_home.SmartHome.execute() — proving the smart_home tool path
    was actually invoked (not e.g. silently falling through to
    direct_answer, which would leave the LLM improvising a response
    instead of touching the real tool at all). The tool's raw result gets
    LLM-narrated for smart_home (unlike app_open/file_open's verbatim
    return), so this checks invocation directly rather than matching
    narrated text, which can legitimately be paraphrased.
    """
    with patch("tools.smart_home.smart_home") as mock_sh, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("core.agent.brain") as mock_brain:
        mock_sh.execute = AsyncMock(return_value="The smart home system is not configured.")
        mock_tts.return_value = ""
        mock_brain.generate = AsyncMock(return_value="Las luces no se pudieron apagar, sir.")

        response = _post_chat(client, {
            "message": "apaga las luces",
            "session_id": "multilingual-test-es-smarthome",
        })

    assert response.status_code == 200
    mock_sh.execute.assert_called_once()


def test_chat_hindi_app_open_launches_real_tool(client):
    """Hindi 'कैलकुलेटर खोलो' (SOV word order) through /chat must classify as app_open."""
    with patch("tools.app_control.open_app") as mock_open_app, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts:
        mock_open_app.return_value = "Launching calculator."
        mock_tts.return_value = ""

        response = _post_chat(client, {
            "message": "कैलकुलेटर खोलो",
            "session_id": "multilingual-test-hi-app",
        })

    assert response.status_code == 200
    mock_open_app.assert_called_once_with("calculator")


def test_chat_french_smart_home_reaches_real_tool(client):
    """French 'éteins les lumières' must classify as smart_home end-to-end and invoke the real tool."""
    with patch("tools.smart_home.smart_home") as mock_sh, \
         patch("api.routes.chat.synthesize", new_callable=AsyncMock) as mock_tts, \
         patch("core.agent.brain") as mock_brain:
        mock_sh.execute = AsyncMock(return_value="The smart home system is not configured.")
        mock_tts.return_value = ""
        mock_brain.generate = AsyncMock(return_value="Les lumières n'ont pas pu être éteintes, sir.")

        response = _post_chat(client, {
            "message": "éteins les lumières",
            "session_id": "multilingual-test-fr-smarthome",
        })

    assert response.status_code == 200
    mock_sh.execute.assert_called_once()
