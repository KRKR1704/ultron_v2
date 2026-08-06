---
id: file_open
name: Open File/Folder
description: >
  Opens a local file or common folder (Downloads, Desktop, Documents) via
  tools/app_control.py. Returns the tool's result verbatim — never
  LLM-paraphrased — so a failure can never be narrated as a fake success.
type: intent
trigger_type: regex
priority: 40
handler: core.agent:_run_file_open
flags:
  requires_grounding: false
  verbatim_response: true
patterns:
  english:
    - '\bopen\b.*\b(the\s+)?(file|folder|directory)\b'
    - '\bshow\s+me\b.*\b(the\s+)?file\b'
    - '\bopen\b.*\bmy\s+(downloads?|desktop|documents?)\b'
    - '\bopen\b.*\.(txt|pdf|docx?|xlsx?|pptx?|csv|jpe?g|png|py|js|json|md|zip|rtf)\b'
  multilingual_latin:
    - '\b(open|launch|start|abre|abrir|ouvre|ouvrir|öffne|öffnen)\b.*\b(file|folder|directory|archivo|carpeta|dossier|fichier|ordner|datei)\b'
  multilingual_script:
    - '((खोलो|खोलें|खोल|తెరువు|తెరవండి|열어|열다|開いて|開く|打开|افتح)|(open|launch|start|abre|abrir|ouvre|ouvrir|öffne|öffnen)).*(फ़ाइल|फोल्डर|폴더|파일|ファイル|フォルダ|文件|文件夹|ملف|مجلد)'
---

# Open File/Folder

Same anti-fabrication pattern as `app_open` (`verbatim_response: true`):
`tools.app_control.open_file_from_command()` already returns a precise,
human-readable outcome ("Opening Documents." / "File not found: X."), and
that string IS the response — no LLM rewrite step, so a failed open can
never be reported as a fake success. See `app_open.SKILL.md` for the
`_APP_NAMES_PATTERN` dynamic-pattern note; `file_open`'s patterns are all
static (no dependency on an external, growable map), so this file has no
equivalent exception.
