"""
vision/analyzer.py — Image analysis via Claude Vision.

Combines OCR-extracted text with a visual analysis call to Claude claude-opus-4-6.
Applies context-specific system prompts for code, documents, foreign text, etc.
"""

import logging
from typing import Optional

from core.brain import brain

log = logging.getLogger(__name__)

# ── Context-specific system prompts ──────────────────────────────────────────

_CONTEXT_PROMPTS: dict[str, str] = {
    "code": (
        "You are analyzing source code visible on screen or in an image. "
        "Identify the language, describe what the code does, spot any bugs or "
        "issues, and suggest improvements. Be concise and precise."
    ),
    "foreign_text": (
        "You are analyzing an image that contains text in a foreign language. "
        "Identify the language, translate all visible text to English, and "
        "provide a clear explanation of the content."
    ),
    "document": (
        "You are analyzing a document image. Summarize its key points, "
        "identify the document type (invoice, contract, letter, etc.), and "
        "extract the most important information."
    ),
    "general": (
        "You are ULTRON analyzing a visual input. Describe what you see "
        "precisely and answer the user's question with sharp, direct insight."
    ),
}


async def analyze(
    image_b64: str,
    question: str,
    context: str = "general",
    session_id: str = "default",
    mode: str = "professional",
    language_code: str = "en",
    ocr_text: str = "",
) -> str:
    """
    Send *image_b64* (base64 JPEG) to Claude Vision and return the analysis.

    *ocr_text* is pre-extracted text from ocr.py — included in the prompt so
    Claude can cross-reference readable text with visual context.

    *context* must be one of: "code", "foreign_text", "document", "general".
    Defaults to "general" for unknown values.
    """
    if not image_b64:
        return "No image was provided for analysis."

    system_suffix = _CONTEXT_PROMPTS.get(context, _CONTEXT_PROMPTS["general"])

    # Build the user message — include OCR text if available
    user_message_parts = [question or "What do you see in this image?"]
    if ocr_text.strip():
        user_message_parts.append(
            f"\n\n[OCR extracted text from image]\n{ocr_text.strip()}"
        )
    user_message = "\n".join(user_message_parts)

    return await brain.analyze_image(
        image_base64=image_b64,
        question=user_message,
        session_id=session_id,
        mode=mode,
        language_code=language_code,
    )
