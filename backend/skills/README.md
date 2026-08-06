# ULTRON Skills — SKILL.md format reference

A "skill" is one tool-triggering intent (or, for `mode_switch`, one tone
classification) defined as data instead of Python code: a `*.SKILL.md`
file with YAML frontmatter + a markdown body. `skills/loader.py` parses
every `*.SKILL.md` file in this directory at startup; `core/agent.py`
(and, for `mode_switch`, `api/routes/chat.py`) build their classifiers from
what's loaded.

**This is still plain regex pattern matching, not a real agent framework.**
Moving the trigger patterns into data files doesn't change the matching
*mechanism* — `re.search(pattern, lowered_text)`, first match wins — it
just means the patterns live somewhere versionable and human-readable
instead of buried in a Python literal, so adding a new skill is a data
change, not a code change.

**Start here:** `web_search.SKILL.md` in this directory is a fully
documented, no-special-cases example — read it alongside this file.

## Minimal example

```yaml
---
id: my_new_skill
name: My New Skill
description: One sentence describing what this skill does.
type: intent              # "intent" (tool-triggering) or "mode_switch"
trigger_type: regex       # "regex" (pattern matching) or "function" (custom Python)
priority: 110              # lower = checked first; must be unique among intent skills
handler: tools.my_module:my_handler_function
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\btrigger phrase one\b'
    - '\banother trigger\b'
---

# My New Skill

Free-form markdown documentation — not parsed, for humans only.
```

Drop this file in `backend/skills/` and restart the backend. No changes to
`core/agent.py` are needed — that's the actual point of this system.

## Field reference

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | The intent name `classify_intent()` returns, e.g. `"web_search"`. Must be unique. |
| `name` | yes | Human-readable name, used in docs/logs only. |
| `description` | yes | One or two sentences — what this skill does. |
| `type` | yes | `"intent"` (the normal case — a tool `core/agent.py` can dispatch to) or `"mode_switch"` (the one special case used by `api/routes/chat.py` — see below). |
| `trigger_type` | intent skills only | `"regex"` (the default — matched via `patterns:`) or `"function"` (matched by calling a Python function — see `calculate.SKILL.md`). |
| `priority` | intent + regex skills | An integer. Lower is checked first. **Matters when two skills' patterns could both match the same input** — e.g. `browser_open` (20) is checked before `app_open` (30) so a domain-bearing phrase like "open youtube.com" doesn't get shadowed by a looser app-name pattern. Existing priorities are spaced by 10 (10, 20, 30, ...) so a new skill can be slotted in between without renumbering everything. |
| `handler` | intent skills only | `"module.path:function_name"` — resolved via `importlib` the first time it's called. The function is normal Python; the skill file just points at it. |
| `trigger_fn` | `trigger_type: function` only | Same `"module.path:function_name"` format — called as `trigger_fn(text) -> Optional[str]`; non-`None` means "this skill matches." |
| `flags.verbatim_response` | optional | If `true`, the handler's return value IS the final response — no LLM rewrite step. Use for tools whose success/failure must never be paraphrased (a launch failure narrated as a fake success is exactly the bug this flag prevents — see `app_open.SKILL.md`/`file_open.SKILL.md`). |
| `flags.requires_grounding` | optional | If `true`, the handler is called with the FULL request context (`text, session_id, mode, language_code, user_name`) and owns its entire response, skipping the generic tool-result → `brain.generate()` narration step. Use for anti-hallucination safeguards like `calculate`'s verify/retry/template-fallback loop — see `calculate.SKILL.md`. |
| `patterns` | `trigger_type: regex` only | A mapping of `group_name -> [pattern, ...]`. Grouping is documentation only (which language(s) a group targets) — matching flattens every group into one list; a match on ANY pattern in ANY group makes the skill match. |

## Handler function signatures

Handlers are called with a **positional** slice of `(text, session_id,
language_code)`, sized to however many parameters the handler actually
declares — e.g. a handler taking one parameter gets `(text,)`, one taking
three gets `(text, session_id, language_code)`. This means the handler's
parameter *names* don't have to match (`camera_analyze`'s handler names its
first parameter `question`, not `text` — that's fine, positional binding
doesn't care), but the *order* and *count* do. `requires_grounding` skills
are the one exception — their handler is always called with the full
5-argument signature `(text, session_id, mode, language_code, user_name)`.

## The one dynamic-pattern exception: `app_open`

Almost every skill's `patterns:` are 100% static data. `app_open` is the
one exception: it needs to match the current list of installed apps
(`tools.app_control.APP_MAP`), which is a live Python dict, not something
that belongs hardcoded into a markdown file (that would recreate the exact
"classifier and app map can drift apart" bug this project's original
multilingual fix pass eliminated). `core/agent.py` appends 4 more patterns,
built from `APP_MAP` at import time, to the `app_open` skill's pattern list
right after loading — see `app_open.SKILL.md`'s own docs for the full
rationale, and `core/agent.py`'s "Skill loading" section for the code.

## `mode_switch` — the other special case

Used only by `api/routes/chat.py` to detect "switch to casual mode" style
commands — a *tone* change, not a tool to run, so it's not part of
`core/agent.py`'s intent classifier. Its `patterns:` field is shaped
differently from every other skill: a single ORDERED list of
`{pattern, target}` entries (`target` is `"casual"` or `"professional"`)
rather than a grouped mapping, because first-match-wins order matters across
the *whole* list here. See `mode_switch.SKILL.md`.

## Multilingual patterns

Several skills combine multiple languages into ONE regex alternation group
(e.g. `web_search`'s `multilingual_latin` group matches English, Spanish,
French, and German search verbs with a single pattern) — this mirrors how
the patterns were originally written in `core/agent.py` before this
migration, and is preserved exactly rather than split into one group per
language, since splitting a shared alternation risks subtly changing which
strings match at the edges. Script languages (Hindi, Telugu, Korean,
Japanese, Chinese, Arabic) are matched as **unanchored substrings**, not
`\bword\b`-bounded — Python's `\b` doesn't reliably find a word boundary
after a Devanagari/Telugu combining vowel mark, and Japanese/Chinese don't
put spaces between words at all, so `\b` silently fails to match there. See
`web_search.SKILL.md`'s body for the full explanation with a verified repro.
