---
id: calculate
name: Calculator
description: >
  Real Python arithmetic evaluation via tools/calculator.py's whitelisted AST
  evaluator (no eval()). The LLM's role is strictly limited to narrating the
  already-computed, verified result — it never computes anything itself.
type: intent
trigger_type: function
trigger_fn: tools.calculator:extract_math_expression
priority: 0
handler: core.agent:_run_calculate_and_narrate
flags:
  requires_grounding: true
patterns: {}
---

# Calculator

## Why this skill is different from every other skill

Every other intent skill is triggered by regex pattern matching against the
lowercased input text. `calculate` is triggered by calling
`tools.calculator.extract_math_expression(text)` directly — if it returns a
string (a cleanly-extracted expression), the intent is `calculate`; if it
returns `None`, this skill does not match at all. This is deliberately NOT a
regex — real arithmetic detection needs to strip framing words ("what is",
"calculate", "divided by", ...), function words, and filler text through a
multi-stage pipeline that a single pattern can't express. See
`tools/calculator.py`'s own docstrings for that pipeline.

`priority: 0` and `trigger_type: function` together mean this skill is
checked FIRST, before any regex-triggered skill and before the conversational
overrides in `core/agent.py` — `extract_math_expression()` is strict enough
(requires actual digits + an operator/function, excludes phone-number/date-
shaped text) that it never spuriously fires on chitchat like "what is my
name" (no digits), so checking it first is safe.

## Grounding safeguard (`requires_grounding: true`)

This flag tells `run_agent()` that the handler
(`core.agent:_run_calculate_and_narrate`) fully owns its own response and
must be called with the complete request context (text, session_id, mode,
language_code, user_name) — NOT the generic tool-result -> single
`brain.generate()` narrate step every other skill uses. The handler:

1. Computes the real answer via `tools.calculator.calculate()`.
2. Sends the LLM a prompt stating the exact verified number and instructing
   it to state it verbatim.
3. Checks the LLM's response actually contains that exact number string.
4. If it drifted, retries once with a more forceful prompt.
5. If it STILL drifted, falls back to a guaranteed-correct template
   (`"The result is {result}, sir."`) — never lets the LLM's own arithmetic
   reach the user.

This exact verify-retry-fallback logic is unchanged Python in
`core/agent.py`'s `_run_calculate_and_narrate()` — this skill file only
declares that it exists and should be invoked this way; it does not
reimplement it declaratively (correctly — this is exactly the kind of
intent-specific safety logic that stays as real code, not config).
