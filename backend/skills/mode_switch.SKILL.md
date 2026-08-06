---
id: mode_switch
name: Mode Switch Detection
description: >
  Detects casual/professional tone-switch commands, multilingual. Used by
  api/routes/chat.py — NOT part of core/agent.py's tool-intent classifier,
  since a mode switch changes HOW Ultron talks, not WHAT tool it runs.
type: mode_switch
patterns:
  # → casual (English)
  - {pattern: '\b(switch|change|go|put|set)\s+(to\s+)?(casual|chill|relax(ed)?|friendly|informal)\b', target: casual}
  - {pattern: '\bcasual\s*(mode)?\b', target: casual}
  - {pattern: '\brelax\s*(mode)?\b', target: casual}
  - {pattern: '\bchill\s*(mode|out)?\b', target: casual}
  - {pattern: '\bbe\s+(more\s+)?(casual|chill|friendly|relaxed|cool|fun)\b', target: casual}
  - {pattern: '\bstop\s+being\s+(so\s+)?(formal|stiff|professional|serious)\b', target: casual}
  - {pattern: '\bgo\s+(casual|informal|easy|fun)\b', target: casual}
  - {pattern: '\bfriendly\s+mode\b', target: casual}
  - {pattern: '\binformal\s+mode\b', target: casual}
  # → professional (English)
  - {pattern: '\b(switch|change|go|put|set)\s+(to\s+)?(professional|pro|formal|business|strict|serious)\b', target: professional}
  - {pattern: '\bprofessional\s*(mode)?\b', target: professional}
  - {pattern: '\bbusiness\s*(mode)?\b', target: professional}
  - {pattern: '\bformal\s*(mode)?\b', target: professional}
  - {pattern: '\bbe\s+(more\s+)?(professional|formal|serious|strict)\b', target: professional}
  - {pattern: '\bback\s+to\s+(professional|formal|pro|business|strict)\b', target: professional}
  - {pattern: '\bpro\s+mode\b', target: professional}
  # Multilingual keywords (transliteration / loan words common across languages)
  # Hindi/Telugu/South Asian languages
  - {pattern: '\bkasual\b', target: casual}
  - {pattern: '\bprofessional\s+mode\b', target: professional}
  # Japanese (romaji)
  - {pattern: '\bkajuaru\b', target: casual}
  - {pattern: '\bpurof[ei]ssel?n?aru?\b', target: professional}
  # Korean (romaji)
  - {pattern: '\bkajeual\b', target: casual}
  # Chinese (romaji)
  - {pattern: '\bsuíbiàn\b', target: casual}
  - {pattern: '\bzhuānyè\b', target: professional}
  # Spanish
  - {pattern: '\b(modo\s+)?(informal|relajado|casual)\b', target: casual}
  - {pattern: '\b(modo\s+)?(profesional|formal|serio)\b', target: professional}
  # French
  - {pattern: '\b(mode\s+)?(décontracté|informel|casual)\b', target: casual}
  - {pattern: '\b(mode\s+)?(professionnel|formel|sérieux)\b', target: professional}
  # German
  - {pattern: '\b(modus\s+)?(locker|lässig|casual|freundlich)\b', target: casual}
  - {pattern: '\b(modus\s+)?(professionell|formell|ernst)\b', target: professional}
  # Arabic
  - {pattern: '\bغير\s+رسمي\b', target: casual}
  - {pattern: '\bرسمي\b', target: professional}
---

# Mode Switch Detection

Reproduces `api/routes/chat.py`'s original `_MODE_SWITCH_PATTERNS` list
**in the exact original order** — a single ordered list of
`{pattern, target}` entries, not split into separate casual/professional
groups. This matters because matching is first-match-wins across the WHOLE
list (`_detect_mode_switch()` loops the list once and returns on the first
pattern that matches) — preserving the exact interleaved order guarantees
byte-identical behavior even for a pathological input that could match a
pattern from both groups.

`api/routes/chat.py` loads this skill via
`skills.loader.load_mode_switch_skill()` and iterates `skill.mode_patterns`
exactly as it used to iterate the hardcoded tuple list.
