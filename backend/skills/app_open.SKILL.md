---
id: app_open
name: Open Application
description: >
  Launches a desktop application via tools/app_control.py's APP_MAP. Returns
  the tool's result verbatim — never LLM-paraphrased — so a launch failure
  can never be narrated as a fake success.
type: intent
trigger_type: regex
priority: 30
handler: core.agent:_run_app_open
flags:
  requires_grounding: false
  verbatim_response: true
has_dynamic_patterns: true
patterns:
  english:
    - '\blaunch\b'
    - '\bstart\b.*(app|application|program)'
foreign_aliases:
  'calculadora': 'calculator'
  'bloc de notas': 'notepad'
  'terminal': 'terminal'
  'calculatrice': 'calculator'
  'bloc-notes': 'notepad'
  'taschenrechner': 'calculator'
  'notizblock': 'notepad'
  'कैलकुलेटर': 'calculator'
  '계산기': 'calculator'
  '電卓': 'calculator'
  '計算機': 'calculator'
  '计算器': 'calculator'
  'الآلة الحاسبة': 'calculator'
  'الحاسبة': 'calculator'
---

# Open Application

## The one dynamic-pattern exception in the whole skill set

`_APP_NAMES_PATTERN` in the original `core/agent.py` is built from
`tools.app_control.APP_MAP.keys()` **at import time**, specifically so that
adding a new app to `APP_MAP` becomes voice/text-triggerable with **zero
additional code changes** — this was the original code's own stated
anti-drift design (`agent.py`'s own comment: "Built from
tools.app_control.APP_MAP so the intent classifier and the actual app map
can never drift apart"). Hardcoding the current 27 app names into this
file's static YAML would reintroduce exactly the drift risk that design
existed to avoid — a new app added to `APP_MAP` would silently NOT be
triggerable until someone remembered to also edit this file.

So: this skill's `patterns:` field only holds its two genuinely static
patterns (`\blaunch\b`, `\bstart\b.*(app|application|program)`).
`core/agent.py` still builds `_APP_NAMES_PATTERN` from `APP_MAP` at module
import time (unchanged existing code) and appends 4 more app-name-dependent
patterns to this skill's `patterns` list right after `load_skills()` runs —
functionally identical to the original code's `_INTENT_PATTERNS` entry for
`app_open`, just split between static YAML (2 patterns) and one dynamic
append step (4 patterns) instead of all 6 being hardcoded Python literals.
Pattern order within a single skill's list does not affect matching (any
match wins), so this split changes nothing behaviorally.

`has_dynamic_patterns: true` is a documentation flag for exactly this —
readers of this file (or future skill authors) should know this is not a
100%-static skill.

## `foreign_aliases`

A handful of generic-word (non-brand-name) app names genuinely translate —
most `APP_MAP` entries are brand names (Spotify, Chrome, Discord, ...) that
don't. This is static data (no drift risk, unlike `APP_MAP` itself), so it
lives directly in this file's frontmatter and is read via `skill.data`. Used
both to extend the classification pattern (combined with `_APP_NAMES_PATTERN`
at the same dynamic-append step above) AND by the `handler`
(`core.agent:_run_app_open`) to resolve a foreign alias like Spanish
"calculadora" to its canonical `APP_MAP` key ("calculator") before calling
`tools.app_control.open_app()`.
