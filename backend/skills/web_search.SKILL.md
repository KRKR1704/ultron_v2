---
id: web_search
name: Web Search
description: >
  Searches the web (Tavily) and summarizes results — for real-time/
  current-events questions the LLM shouldn't answer from stale training data.
type: intent
trigger_type: regex
priority: 10
handler: core.agent:_run_web_search
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bsearch (for |the web |about )?\w'
    - '\blook up\b'
    - '\blatest\b'
    - '\bnews (on|about|for)\b'
    - '\btell me about [a-zA-Z]'
    - '\bwhat is the (current|latest|recent|today''?s|live)\b'
    - '\bwhat''?s (happening|going on|new|trending)\b'
    - '\bwho is [A-Z]'
    - '\bwhere is\b'
    - '\bwhen (is|was|did|does)\b'
  multilingual_latin:
    - '\b(search|busca|buscar|cherche|chercher|recherche|suche)\b'
  multilingual_script:
    - '(खोजो|खोजें|ढूंढो|ढूंढें|వెతకు|검색|検索|搜索|ابحث)'
---

# Web Search

This is the fully-documented reference example — see `skills/README.md` for
the format walkthrough this file illustrates.

## What it does

Routes to `tools/web_search.py`'s Tavily-backed search, then hands the
result to `brain.generate()` to summarize naturally (the `handler` function,
`core.agent:_run_web_search`, strips leading intent words like "search for"
before calling the tool — see its body).

## Fields explained

- `type: intent` — a tool-triggering intent handled by `core/agent.py`'s
  `classify_intent()`/`run_agent()` (as opposed to `type: mode_switch`,
  which is a separate classification used only by `api/routes/chat.py`).
- `trigger_type: regex` — matched via `re.search(pattern, lowered_text)`,
  same mechanism every regex-triggered skill uses. (The one exception in the
  whole skill set is `calculate`, which uses `trigger_type: function`.)
- `priority: 10` — the lowest priority number among the regex-triggered
  skills, so `web_search` is checked first among them. This reproduces the
  exact order of the original hardcoded `_INTENT_PATTERNS` list in
  `core/agent.py`, where list position determined which intent won when text
  could plausibly match more than one pattern group.
- `handler: core.agent:_run_web_search` — a `module.path:function_name`
  reference, resolved via `importlib` at classification time. The function
  itself is unchanged Python, still living in `core/agent.py`.
- `flags` — `requires_grounding` and `verbatim_response` are both `false`
  here: this skill's tool result gets normally narrated by the LLM (unlike
  `calculate`'s grounding safeguard or `app_open`/`file_open`'s verbatim
  return).
- `patterns` — a mapping of group name -> list of regex strings. Grouping is
  purely for human readability (which language(s) a group targets); matching
  itself flattens every group into one list and returns a match if ANY
  pattern in ANY group matches — order between groups doesn't affect
  matching, only order between DIFFERENT skills' `priority` does.

## On the "multilingual_latin" / "multilingual_script" split

This mirrors the legacy `core/agent.py` design exactly: `multilingual_latin`
combines English/Spanish/French/German search verbs into ONE alternation
regex (they're all safe to wrap in `\b...\b` word boundaries), while
`multilingual_script` combines Hindi/Telugu/Korean/Japanese/Chinese/Arabic
search words into a separate group matched as plain unanchored substrings
(no `\b` — Python's `\b` doesn't reliably find a boundary after a Devanagari/
Telugu combining vowel mark, and Japanese/Chinese don't put spaces between
words at all). These are the exact same regex strings that existed in
`agent.py`'s `_MULTI_SEARCH` / `_MULTI_SEARCH_SCRIPT` constants — copied
verbatim, not re-derived, since even a cosmetic-looking change to a regex
alternation can change matching behavior at the edges.
