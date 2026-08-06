---
id: type_text
name: Type Text
description: >
  Types literal text into whatever window currently has OS focus, via
  tools/browser_control.py's pyautogui-backed type_text().
type: intent
trigger_type: regex
priority: 50
handler: core.agent:_run_type_text
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\btype\b'
    - '\bwrite this\b'
    - '\benter this\b'
    - '\bpaste\b'
---

# Type Text

Not one of the 10 intents explicitly named in this migration's task brief —
it's an 11th, pre-existing intent found live in `core/agent.py`'s
`_INTENT_PATTERNS` during the audit for this migration. Migrated anyway
rather than silently dropped, to avoid a real (if untested-by-name)
behavior regression. English-only in the legacy code — no multilingual
pattern group exists for this intent, so none is added here either (faithful
port, not an enhancement).
