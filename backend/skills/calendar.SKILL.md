---
id: calendar
name: Calendar
description: >
  Schedules/lists calendar events via tools/calendar_tasks.py's Google
  Calendar integration (gracefully reports "not configured" when
  credentials.json is absent).
type: intent
trigger_type: regex
priority: 70
handler: core.agent:_run_calendar
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bschedule\b'
    - '\bmeeting\b'
    - '\bcalendar\b'
    - '\bappointment\b'
    - '\bevent\b'
    - '\bbook\b.*\btime\b'
  multilingual_latin:
    - '\b(meeting|reunión|reunion|agenda|cita|réunion|rendez-vous|termin|besprechung)\b'
  multilingual_script:
    - '(बैठक|मीटिंग|कार्यक्रम|회의|会議|会议|اجتماع)'
---

# Calendar

`handler` takes `(text, session_id)` positionally — dispatched via
`run_agent()`'s generic positional-slicing mechanism (see
`skills/README.md`), same as `tasks`/`smart_home`.
