# ULTRON — Failing Test Triage Report

Generated: 2026-07-22
Project location: `D:\Ultron_V2\ultron_v2\backend`
Scope: investigation and reporting only — **no source, test, or fixture files were modified**.

## How this was produced

```
cd backend
.venv\Scripts\activate   (venv is at project root, not inside backend/ — see backend/README.md)
pytest tests/ -v --tb=short > test_output_full.txt 2>&1
pytest tests/ -v --tb=long -x --lf > test_output_failures_detail.txt 2>&1
```

Both files are saved in `backend/` alongside this report. Note: `-x` did not actually stop the run early — all 10 previously-failed tests still ran and are captured with full tracebacks in `test_output_failures_detail.txt` (`10 failed in 3.34s`). Every finding below is backed by an exact excerpt from that file.

Full-suite result: **147 passed, 10 failed, 2 skipped** — identical to the state reported at the end of the last fix pass.

---

## Summary Table

| Test Name | File | Category | Confidence | Related to last fix pass? |
|---|---|---|---|---|
| `test_mode_switch_to_casual_success` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_to_professional_success` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_clears_memory` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_updates_config` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_returns_confirmation_audio` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_case_insensitive` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_brain_failure_uses_fallback` | `tests/test_07_mode.py` | [A] Stale test | High | No |
| `test_mode_switch_then_chat_uses_new_mode` | `tests/test_19_integration.py` | [A] Stale test | High | No |
| `test_mode_persists_after_config_reload` | `tests/test_19_integration.py` | [A] Stale test | High | No |
| `test_status_reflects_config_mode` | `tests/test_19_integration.py` | [A] Stale test | Medium-High | No |

## Category Breakdown

- [A] Stale tests: **10**
- [B] Real bugs: 0
- [C] Missing config/credentials: 0
- [D] Test environment issues: 0
- [E] Known out-of-scope (TTS): 0

All 10 failures collapse into exactly **two** distinct root causes:

1. **9 tests** (all 7 in `test_07_mode.py`, plus 2 of the 3 failing in `test_19_integration.py`) fail identically at `patch("api.routes.mode.brain")` — `api/routes/mode.py` has no module-level name `brain`. It never did anything with `brain` at all in the code as it exists today; `/mode` builds its confirmation line from a hardcoded list (`_PROFESSIONAL_LINES` / `_CASUAL_LINES` + `random.choice()`), not an LLM call.
2. **1 test** (`test_status_reflects_config_mode`) fails at `patch("api.routes.status.camera_capture")` — `api/routes/status.py` imports `camera_capture`, `screen_capture`, and `wake_word_detector` *inside* the `status()` function body, not at module level, so there's no module attribute to patch.

Both are `AttributeError` raised by `unittest.mock`'s `_patch.__enter__()` **before the HTTP request is even made** — none of these tests get far enough to exercise the actual `/mode` or `/status` route logic at all. This also means none of them could possibly be affected by anything in the last fix pass, since the failure happens at test setup, not inside any code path that pass touched (confirmed independently below).

---

## Detailed Findings

### `test_mode_switch_to_casual_success`
- File: `tests/test_07_mode.py:19`
- Category: **[A] Stale test**
- Confidence: **High**
- Error:
  ```
  with patch("api.routes.mode.brain") as mock_brain, \
       patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
  ...
  E   AttributeError: <module 'api.routes.mode' from 'D:\\Ultron_V2\\ultron_v2\\backend\\api\\routes\\mode.py'> does not have the attribute 'brain'
  D:\python_3.11\Lib\unittest\mock.py:1419: AttributeError
  ```
- Explanation: The test file's own docstring says *"Mocks brain.generate and synthesize to avoid real LLM/TTS calls"* — this describes an **earlier** version of `/mode` that presumably called `core.brain.brain.generate()` to produce a personalized, LLM-written confirmation message. The current `api/routes/mode.py` (read in full) does not import `brain` anywhere. Its own docstring states the design explicitly: *"Confirmation lines are hardcoded — no LLM call needed for a one-liner. This makes the mode switch feel instant (TTS only, ~1 second)."* It picks a random line from `_PROFESSIONAL_LINES` / `_CASUAL_LINES` via `random.choice()`. This is a deliberate, and — per the live audit two passes ago — a *working and verified-correct* design (confirmed via `curl`: `POST /mode {"mode":"casual"}` → real 200 with a genuine in-character line, no LLM round-trip latency). The test was simply never updated when the endpoint was rewritten to skip the LLM call.
- What specifically changed: `/mode`'s confirmation-message generation went from (presumably) "ask the LLM" to "pick a random pre-written line." The test still assumes the former.
- Regression check: **No.** `api/routes/mode.py` does not appear in `git status --short` (it has zero uncommitted changes — see Step 3 below) and was not touched, read, or referenced by any of the 9 fixes in the last pass.
- Recommended action: **Fix test** — either delete the `brain` patch (nothing to mock; `synthesize` alone is sufficient) or, if the intent is to keep mocking *something* LLM-related for future-proofing, patch `random.choice` instead to make the confirmation line deterministic for assertions.

### `test_mode_switch_to_professional_success`
- File: `tests/test_07_mode.py:34`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Identical `AttributeError: <module 'api.routes.mode' ...> does not have the attribute 'brain'` at the same `patch()` call (`tests/test_07_mode.py:36`).
- Explanation: Same root cause as above — this test's only difference is switching to "professional" instead of "casual"; it hits the exact same missing-attribute wall before any assertion runs.
- Regression check: No — same reasoning as above.
- Recommended action: Fix test (same as above).

### `test_mode_switch_clears_memory`
- File: `tests/test_07_mode.py:55`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_07_mode.py:63`.
- Explanation: This test actually wants to verify a *different, real* behavior — that `POST /mode` clears conversation memory (`memory.clear_all()`, confirmed present in `api/routes/mode.py:69` and independently verified live in the original audit: "Mode switched %s → %s. All session memories cleared." was logged and behaviorally confirmed). That real behavior is intact and correct; the test never reaches its own assertion (`memory.get_history(...) == []`) because it dies at the same stale `brain` patch first.
- Regression check: No.
- Recommended action: Fix test (remove the `brain` patch). The underlying memory-clearing behavior does not need re-verification — it was independently confirmed working via `curl` during the last audit and the code path is unchanged.

### `test_mode_switch_updates_config`
- File: `tests/test_07_mode.py:74`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_07_mode.py:76`.
- Explanation: Same pattern — intends to verify `app_state["config"]["mode"]` updates after a switch (real, working behavior, confirmed live via `/status` polling in the audit), but never gets there.
- Regression check: No.
- Recommended action: Fix test (remove the `brain` patch).

### `test_mode_switch_returns_confirmation_audio`
- File: `tests/test_07_mode.py:93`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_07_mode.py:95`.
- Explanation: Wants to verify the response JSON has a `confirmation_audio` string field (it does — `ModeResponse.confirmation_audio: str = ""`, unchanged). Dies at the same stale patch before checking it.
- Regression check: No.
- Recommended action: Fix test (remove the `brain` patch; keep the `synthesize` mock, which is real and needed).

### `test_mode_switch_case_insensitive`
- File: `tests/test_07_mode.py:107`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_07_mode.py:109`.
- Explanation: Wants to verify `mode.py:54`'s `request.mode.lower().strip()` handles `"CASUAL"` correctly (it does — confirmed by reading `switch_mode()`). Dies at the same stale patch.
- Regression check: No.
- Recommended action: Fix test (remove the `brain` patch).

### `test_mode_switch_brain_failure_uses_fallback`
- File: `tests/test_07_mode.py:121`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_07_mode.py:126`.
- Explanation: This one is worth calling out specifically — its entire premise ("if `brain.generate` raises, the route must use a hardcoded fallback message") describes a code path that **does not exist** in the current `/mode` implementation, because there is no `brain.generate()` call to raise from in the first place. This isn't just a stale mock target; the *scenario itself* no longer applies to the current design. There is nothing to "fix forward" here except deleting or rewriting the test, since the failure mode it's guarding against can't occur anymore (there's no LLM call on this path to fail).
- Regression check: No.
- Recommended action: **Delete or rewrite this test** — its premise is obsolete, not just its mocking mechanics.

### `test_mode_switch_then_chat_uses_new_mode`
- File: `tests/test_19_integration.py:58`
- Category: **[A] Stale test**
- Confidence: **High**
- Error:
  ```
  with patch("api.routes.mode.brain") as mock_brain, \
       patch("api.routes.mode.synthesize", new_callable=AsyncMock) as mock_tts:
  ...
  E   AttributeError: <module 'api.routes.mode' from '...\\api\\routes\\mode.py'> does not have the attribute 'brain'
  ```
  (at `tests/test_19_integration.py:65`)
- Explanation: An integration test chaining `/mode` → `/chat`. It dies at the exact same stale `api.routes.mode.brain` patch in its own Step 1, before ever reaching the `/chat` call in Step 2 (which patches `api.routes.chat.run_agent` and `api.routes.chat.synthesize` — both real, both correctly present at module level in `chat.py`, confirmed by reading the file: `from core.agent import run_agent` and `from voice.tts import synthesize` are genuine module-level imports there). This confirms the failure is 100% isolated to the `/mode` step's stale mock, not anything in `/chat`.
- Regression check: **No** — and specifically confirmed: the test never reaches the `/chat` call, so it's impossible for this failure to involve `core/agent.py` (app_open regex change) or `multilingual/language_detector.py` (language detection change) or any other file touched last pass — the `AttributeError` fires and aborts the test before those code paths could run at all.
- Recommended action: Fix test — remove the `brain` patch from both the Step 1 and the "Restore" block at the bottom of the test.

### `test_mode_persists_after_config_reload`
- File: `tests/test_19_integration.py:191`
- Category: **[A] Stale test**
- Confidence: **High**
- Error: Same `AttributeError` at `tests/test_19_integration.py:209`, inside a `with _patch("main._CONFIG_PATH", tmp_path), _patch("api.routes.mode.brain") as mock_brain, ...` block.
- Explanation: Wants to verify that after a mode switch, `save_config()` persisted the change to disk and a fresh `load_config()` picks it up (real, correct, working behavior — confirmed structurally in the last audit and independently reproduced live in this session by killing and restarting the actual backend process, which came back up already in `casual` mode). The test dies at the stale `brain` patch before it ever gets to write or reload the temp config file, so its actual subject (config persistence) is never exercised by this test at all right now.
- Regression check: No.
- Recommended action: Fix test — remove the `brain` patch. The persistence behavior itself doesn't need re-fixing; it works (see Recommended Next Steps).

### `test_status_reflects_config_mode`
- File: `tests/test_19_integration.py:239`
- Category: **[A] Stale test** (see nuance below)
- Confidence: **Medium-High**
- Error:
  ```
  with patch("api.routes.status.camera_capture") as mock_cam, \
       patch("api.routes.status.screen_capture") as mock_screen, \
       patch("api.routes.status.wake_word_detector") as mock_wwd:
  ...
  E   AttributeError: <module 'api.routes.status' from '...\\api\\routes\\status.py'> does not have the attribute 'camera_capture'
  ```
  (at `tests/test_19_integration.py:243`)
- Explanation: This is a *different* flavor of the same underlying problem as the other 9, so it earns its own explanation. `api/routes/status.py`'s `status()` handler imports its three dependencies **locally, inside the function body**:
  ```python
  async def status():
      from main import app_state
      from vision.camera import camera_capture
      from vision.screen import screen_capture
      from voice.wake_word import wake_word_detector
      ...
  ```
  Because these names are bound only inside the function's local scope when it runs, `api.routes.status` (the *module*) never has `camera_capture` etc. as attributes to patch — `unittest.mock.patch()` needs a module- or class-level attribute to replace. Patching `api.routes.status.camera_capture` is a no-op target that doesn't exist, so it raises before the request is even sent.
  Two things are worth being precise about:
  1. **The behavior actually under test is correct.** `GET /status` reflecting `app_state["config"]["mode"]` was independently verified live multiple times in the last two sessions (`curl http://localhost:8000/status` after mode switches, and again after a full process restart) — this isn't in question.
  2. **The test's own assertion doesn't even use the mocked values.** The test only asserts `resp.json()["mode"] == "casual"` — it never checks `camera_active`/`screen_active`/`wake_word_active`. The three mocks appear to exist purely so the test doesn't touch real camera/screen/wake-word hardware state during an assertion that doesn't need them at all. This makes the mocking not just stale but arguably unnecessary for what the test is actually trying to prove.
- Regression check: No — `api/routes/status.py` has zero uncommitted changes (confirmed below) and was not part of the last fix pass.
- Recommended action: **Fix test** — the simplest correct fix is to delete the three `patch()` calls entirely, since the assertion never uses `mock_cam`/`mock_screen`/`mock_wwd`. If future tests do need to control camera/screen/wake-word state, `status.py`'s imports would need to move to module level first (a separate, larger decision about that module's structure — not required just to fix this test).

---

## Cross-Check Against the Last Fix Pass

The last fix pass touched exactly these backend files (confirmed via `git status --short backend/`, since the repo has a single initial commit and no further history to diff against):

```
 M backend/api/models.py
 M backend/api/routes/chat.py
 M backend/api/routes/vision.py
 M backend/api/routes/voice.py
 M backend/api/websocket.py
 M backend/core/agent.py
 M backend/main.py
 M backend/multilingual/language_detector.py
 M backend/tools/app_control.py
 M backend/vision/ocr.py
?? backend/api/routes/weather.py
```

**`backend/api/routes/mode.py` and `backend/api/routes/status.py` are not in this list — neither was read, edited, nor referenced by any of the 9 fixes.** Cross-referencing each failing test's actual failure point against this list:

- The 9 `api.routes.mode.brain`-related failures all die at a `patch()` call targeting `mode.py`, a file untouched by the last pass. **Confirmed unrelated.**
- `test_mode_switch_then_chat_uses_new_mode` is the one test that *would* have touched `chat.py` (modified last pass, for the language-detection session-ID threading) in its Step 2 — but it never reaches Step 2, because it fails in Step 1's `mode.py` patch first. **Confirmed unrelated, and confirmed *why* it's unrelated (the failure happens before the changed code path would even run), not just asserted.**
- `test_status_reflects_config_mode` dies at a `patch()` call targeting `status.py`, also untouched by the last pass. **Confirmed unrelated.**

Additionally: these exact 10 test names were already failing in the very first full pytest run of this whole engagement — the original, pre-fix-pass audit baseline was **11 failed** (`146 passed, 11 failed, 2 skipped`), and the 11th was `test_08_voice.py::test_voice_missing_audio_returns_422`, which the last pass fixed (now passing, bringing the count to 147/10/2). All 10 tests in this report were present in that original baseline, before a single line of application code was touched. **None of these 10 are new; none are regressions.**

---

## Recommended Next Steps

**Fix immediately (stale tests, trivial):**
- `test_mode_switch_to_casual_success`, `test_mode_switch_to_professional_success`, `test_mode_switch_clears_memory`, `test_mode_switch_updates_config`, `test_mode_switch_returns_confirmation_audio`, `test_mode_switch_case_insensitive`, `test_mode_switch_then_chat_uses_new_mode`, `test_mode_persists_after_config_reload` — remove the `patch("api.routes.mode.brain")` context manager from each (keep the `synthesize` patch, which is real and needed). Each test's actual assertion is checking real, working behavior and just needs the dead mock removed to reach it.
- `test_status_reflects_config_mode` — remove the three `patch("api.routes.status....")` calls; the assertion doesn't use them.

**Rewrite rather than trivially patch:**
- `test_mode_switch_brain_failure_uses_fallback` — its scenario ("brain.generate raises") can't occur in the current design at all. Either delete it, or repurpose it to test a failure mode that's actually reachable today (e.g., `synthesize` raising, or an invalid `random.choice()` edge case — though there isn't an obvious real failure path left in this simplified, LLM-free implementation).

**Fix in next code pass (real bugs):** None found. Zero of the 10 failures are application bugs.

**Leave skipped/marked until config available (missing credentials):** None of the 10 — this category applies to other, already-passing-or-skipped tests elsewhere in the suite (e.g. `test_12_smart_home.py::test_live_smart_home_turn_on_light`, `test_14_tts.py::test_piper_binary_present_and_runs`), not to any of these 10.

**Investigate further (low confidence / flaky):** None — every one of the 10 has a High or Medium-High confidence, single, unambiguous root cause with a direct code citation. Nothing here needs more investigation before someone acts on it.

**Not recommended:** Do not treat any of these 10 as evidence the last fix pass broke something — the cross-check above is conclusive that all 10 predate it and touch files it never modified.
