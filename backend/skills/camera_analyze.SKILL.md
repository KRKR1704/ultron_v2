---
id: camera_analyze
name: Camera Analysis
description: >
  Captures a live camera frame and analyzes it via Claude Vision + OCR
  (vision/camera.py, vision/ocr.py, vision/analyzer.py).
type: intent
trigger_type: regex
priority: 90
handler: core.agent:_run_camera_analyze
flags:
  requires_grounding: false
  verbatim_response: false
patterns:
  english:
    - '\bwhat do you see\b'
    - '\blook at this\b'
    - '\banalyze this\b'
    - '\bwhat''s in front\b'
    - '\bwhat am i holding\b'
    - '\bcamera\b'
  multilingual_latin:
    - '\b(camera|cámara|camara|caméra|kamera)\b'
  multilingual_script:
    - '(कैमरा|카메라|カメラ|摄像头|相机|كاميرا)'
---

# Camera Analysis

`handler` (`core.agent:_run_camera_analyze`) takes 3 positional parameters
`(question, session_id, language_code="en")` — note the first parameter is
named `question`, not `text`. Dispatch is by POSITION, not by parameter
name (`run_agent()` calls
`handler(*(text, session_id, language_code)[:param_count])`), so the name
mismatch is harmless — this reproduces the original hardcoded call site
`_run_camera_analyze(text, session_id, language_code)` exactly.
