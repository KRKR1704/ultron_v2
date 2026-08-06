---
id: browser_open
name: Open Browser/URL
description: >
  Opens a URL or site (via tools/browser_control.py's site map and
  search-URL templates), distinct from app_open (known desktop apps).
type: intent
trigger_type: regex
priority: 20
handler: core.agent:_run_browser_open
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bopen\b.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)'
    - '\bgo to\b'
    - '\bpull up\b'
    - '\bnavigate to\b'
    - '\bsearch youtube\b'
    - '\bsearch reddit\b'
    - '\bsearch google\b'
  multilingual_latin:
    - '\b(open|launch|start|abre|abrir|ouvre|ouvrir|öffne|öffnen)\b.*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)'
  multilingual_script:
    - '(खोलो|खोलें|खोल|తెరువు|తెరవండి|열어|열다|開いて|開く|打开|افتح).*(\.com|\.org|\.io|\.net|youtube|reddit|github|google|twitter|x\.com)'
---

# Open Browser/URL

`priority: 20` — checked right after `web_search` (10) and before
`app_open` (30), reproducing the exact original list order. This matters
because `browser_open` and `app_open` patterns can both plausibly match the
same input (e.g. "open chrome" — no domain/site keyword, so `browser_open`'s
patterns don't fire, but a domain-bearing phrase like "open youtube.com"
matches `browser_open` before `app_open` ever gets a chance, exactly as
before).
