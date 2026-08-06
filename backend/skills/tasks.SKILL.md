---
id: tasks
name: Tasks
description: >
  Adds/lists to-do items via tools/calendar_tasks.py's Google Tasks
  integration (gracefully reports "not configured" when credentials.json
  is absent).
type: intent
trigger_type: regex
priority: 80
handler: core.agent:_run_tasks
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\btask\b'
    - '\bremind me\b'
    - '\bto[- ]do\b'
    - '\badd to my list\b'
    - '\bcomplete\b.*\btask\b'
    - '\bfinish\b.*\btask\b'
    - '\blist.*tasks?\b'
  multilingual_latin:
    - '\b(remind me|task|recuérdame|recuerdame|tarea|pendiente|rappelle-moi|tâche|tache|erinnere mich|aufgabe)\b'
  multilingual_script:
    - '(याद दिलाओ|टास्क|할일|タスク|リマインド|مهمة|تذكير)'
---

# Tasks

`handler` takes `(text, session_id)` positionally — dispatched via
`run_agent()`'s generic positional-slicing mechanism (see
`skills/README.md`), same as `calendar`/`smart_home`.
