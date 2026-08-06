---
id: smart_home
name: Smart Home Control
description: >
  Turns devices on/off, adjusts temperature, etc. via tools/smart_home.py's
  Home Assistant REST integration (gracefully reports "not configured" when
  HASS_TOKEN is unset, rather than crashing).
type: intent
trigger_type: regex
priority: 60
handler: core.agent:_run_smart_home
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bturn on\b'
    - '\bturn off\b'
    - '\blights?\b'
    - '\bthermostat\b'
    - '\btemperature\b'
    - '\bfan\b'
    - '\bplug\b'
    - '\bswitch\b'
    - '\bdim\b'
    - '\bbrighten\b'
  multilingual_latin:
    - '\b(turn on|enciende|encender|allume|allumer|einschalten)\b'
    - '\b(turn off|apaga|apagar|éteins|éteindre|ausschalten)\b'
    - '\b(lights?|luces|lumières|lichter)\b'
  multilingual_script:
    - '(चालू करो|जलाओ|వెలిగించు|켜|つけて|点けて|شغل)'
    - '(बंद करो|ఆపు|꺼|消して|أطفئ)'
    - '(लाइट|रोशनी|దీపాలు|불|أضواء)'
---

# Smart Home Control

Classification-level multilingual coverage only (per the legacy code's own
documented scope) — `tools/smart_home.py`'s own `_ACTION_MAP`/
`_ENTITY_ALIASES` string-matching stays English-only. Not a live-blocking
gap: with `HASS_TOKEN` unset, `execute()` returns its graceful "not
configured" message before ever reaching that parsing step regardless of
language. If `HASS_TOKEN` is ever configured, `tools/smart_home.py` itself
would still need extending for non-English on/off phrasing to actually
control a device — same caveat the original fix pass documented.
