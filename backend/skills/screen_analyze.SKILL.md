---
id: screen_analyze
name: Screen Analysis
description: >
  Captures a screenshot and analyzes it via Claude Vision + OCR + content-type
  detection (code / foreign_text / document / general) — vision/screen.py,
  vision/ocr.py, vision/analyzer.py, core/agent.py's _detect_screen_context().
type: intent
trigger_type: regex
priority: 100
handler: core.agent:_run_screen_analyze
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bwhat''?s on (the )?screen\b'
    - '\bexplain this\b'
    - '\bwhat am i looking at\b'
    - '\bread (the )?screen\b'
    - '\bscreen\b'
  multilingual_latin:
    - '\b(screen|pantalla|écran|ecran|bildschirm)\b'
  multilingual_script:
    - '(स्क्रीन|화면|画面|屏幕|الشاشة)'
---

# Screen Analysis

Lowest priority among the regex-triggered intents (`priority: 100`) — the
last one checked, reproducing its position at the end of the original
`_INTENT_PATTERNS` list. Same positional-dispatch note as
`camera_analyze.SKILL.md`: `handler`'s first parameter is named `question`,
not `text`, and that's fine since dispatch is by position.
