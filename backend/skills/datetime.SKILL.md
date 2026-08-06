---
id: datetime
name: Date & Time
description: >
  Real current date/time (local system clock) and relative day-count
  calculations ("how many days until Friday"), computed by Python — never
  guessed by the LLM, which has no live clock and a training-data cutoff.
type: intent
trigger_type: regex
priority: 5
handler: core.agent:_run_datetime_and_narrate
flags:
  requires_grounding: true
patterns:
  english:
    - '\bwhat(?:''s| is) (today''?s date|the date today|the current date)\b'
    - '\bwhat (day|date) is it\b'
    - '\bwhat''?s the date\b'
    - '\bcurrent date\b'
    - '\bwhat time is it\b'
    - '\bwhat''?s the time\b'
    - '\bcurrent time\b'
    - '\bwhat day of the week\b'
    - '\bhow many days?\s+(until|till|to|before)\b'
    - '\btell me (today''?s date|the time|the date)\b'
  multilingual_latin:
    # Spanish
    - '\bqué hora es\b'
    - '\bqué día es hoy\b'
    - '\bcuál es la fecha\b'
    - '\bfecha de hoy\b'
    - '\bcuántos días faltan para\b'
    # French
    - '\bquelle heure est-il\b'
    - '\bquel jour sommes-nous\b'
    - '\bquelle est la date\b'
    - '\bdate d''aujourd''hui\b'
    - '\bcombien de jours (avant|jusqu''à)\b'
    # German
    - '\bwie spät ist es\b'
    - '\bwelcher tag ist heute\b'
    - '\bwas ist das datum\b'
    - '\bheutiges datum\b'
    - '\bwie viele tage bis\b'
  multilingual_script:
    # Hindi
    - 'आज की तारीख'
    - 'अभी क्या समय'
    - 'समय क्या है'
    - 'आज कौन सा दिन'
    # Telugu
    - 'ఈ రోజు తేదీ'
    - 'ఇప్పుడు సమయం'
    # Korean
    - '오늘 날짜'
    - '지금 몇 시'
    # Japanese
    - '今日の日付'
    - '今何時'
    # Chinese
    - '今天几号'
    - '今天日期'
    - '现在几点'
    # Arabic
    - 'التاريخ اليوم'
    - 'كم الساعة'
---

# Date & Time

## The gap this fixes

Before this skill existed, "what is today's date" / "what time is it" fell
through every existing pattern straight to `direct_answer`, and the LLM
correctly (from its own perspective — it genuinely has no live clock and a
training-data cutoff) refused: *"I don't have access to real-time data,
including today's date."* This is the exact same class of problem
`calculate` solves for arithmetic — the fix is the same shape: compute the
real answer in Python, never let the LLM guess.

## `priority: 5` — checked before `web_search` (10), deliberately

`web_search.SKILL.md` has the pattern
`\bwhat is the (current|latest|recent|today'?s|live)\b`, which would
otherwise catch "what is the current time"/"what is today's date" first and
route them to a live web search instead of the local system clock. Placing
this skill at a lower priority number means it's checked first, so those
phrasings correctly resolve to `datetime`, not `web_search`.

## False-positive guard: never a bare `\bdate\b`

No pattern here matches on the word "date" alone — every English pattern
requires it in a specific question frame ("what's the date", "today's
date", "current date"). This is deliberate: "I have a date tonight" (a
romantic date) must never trigger this skill, and a bare `\bdate\b` pattern
would have caught it. Verified directly — see
`test_datetime_skill_does_not_misfire_on_romantic_date` in
`tests/test_27_datetime.py`.

## Two sub-cases, one skill, one handler

Unlike most skills, this one's trigger patterns cover two different
question shapes that both route to the same `datetime` intent — the
HANDLER (`core.agent:_run_datetime_and_narrate`), not the classifier,
decides which applies, via `tools.datetime_tool.extract_days_until_target()`:

1. **Simple current date/time** ("what time is it", "what's today's date")
   — narrates `tools.datetime_tool.get_current_datetime_fact()`.
2. **Relative day count** ("how many days until Friday") — narrates
   `tools.datetime_tool.days_until()`, which resolves the target phrase via
   `dateparser` (already a project dependency, see
   `tools/calendar_tasks.py`) and computes a real calendar-day difference.

## Grounding safeguard (`requires_grounding: true`) — one deliberate deviation

Same verify/retry/template-fallback pattern as `calculate`, with one
disclosed difference: `calculate` verifies the LLM's response contains the
exact numeric result string, because a bare number is language-neutral.
Formatted dates aren't — the day/month NAMES are English words, but the
system prompt forces the response into whatever language was detected, so
demanding the literal word "Thursday" survive inside a Spanish response
would be unreasonable. Verification here instead checks for the **digit-only
anchors** (year, day-of-month) — those *are* language-neutral and will
naturally appear in a translated date phrase too (e.g. "jueves, 6 de agosto
de 2026" still contains "2026" and "6"). See
`tools/datetime_tool.py`'s `get_current_datetime_fact()` docstring for the
full rationale.
