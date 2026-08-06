"""
test_26_skills_loader.py — Tests for skills/loader.py and the SKILL.md-driven
migration of core/agent.py's intent classifier + api/routes/chat.py's
mode-switch detector.

These tests protect the declarative-skills refactor itself (loader
correctness, priority ordering, handler/trigger_fn resolution). The
regression protection for classification BEHAVIOR being unchanged is
test_05_intent.py, test_17_agent.py, test_20_calculator.py, and
test_23_multilingual_intent.py — all still passing unmodified is the real
evidence there; this file is about the plumbing.
"""

from pathlib import Path

import pytest

from skills.loader import Skill, load_mode_switch_skill, load_skills

_SKILLS_DIR = Path(__file__).parent.parent / "skills"

# Reproduces core/agent.py's original hardcoded _INTENT_PATTERNS list order —
# see agent.py's module docstring / skills/README.md for why this exact
# order is safety-critical (first-match-wins across different intents).
# "datetime" (priority 5) was added later, deliberately checked BEFORE
# web_search (10) — see skills/datetime.SKILL.md for why (a web_search
# pattern would otherwise swallow "what is the current time").
_EXPECTED_PRIORITY_ORDER = [
    "datetime", "web_search", "browser_open", "app_open", "file_open", "type_text",
    "smart_home", "calendar", "tasks", "camera_analyze", "screen_analyze",
]


def test_loads_exactly_twelve_intent_skills():
    skills = load_skills()
    ids = {s.id for s in skills}
    assert ids == {
        "calculate", "datetime", "web_search", "browser_open", "app_open",
        "file_open", "type_text", "smart_home", "calendar", "tasks",
        "camera_analyze", "screen_analyze",
    }
    assert len(skills) == 12


def test_priority_order_reproduces_legacy_intent_patterns_order():
    skills = load_skills()
    regex_skills = [s for s in skills if s.trigger_type == "regex"]
    assert [s.id for s in regex_skills] == _EXPECTED_PRIORITY_ORDER
    # load_skills() itself returns skills already sorted by priority.
    assert [s.priority for s in regex_skills] == sorted(s.priority for s in regex_skills)


def test_calculate_is_the_only_function_triggered_skill():
    skills = load_skills()
    function_skills = [s for s in skills if s.trigger_type == "function"]
    assert [s.id for s in function_skills] == ["calculate"]


def test_every_intent_skill_handler_resolves_to_a_real_callable():
    skills = load_skills()
    for skill in skills:
        fn = skill.resolve_handler()
        assert callable(fn), f"{skill.id}'s handler did not resolve to a callable"


def test_calculate_trigger_fn_round_trips_through_extract_math_expression():
    skills = load_skills()
    calc = next(s for s in skills if s.id == "calculate")
    trigger_fn = calc.resolve_trigger_fn()

    from tools.calculator import extract_math_expression
    assert trigger_fn is extract_math_expression

    assert trigger_fn("what is 5 plus 3") == "5+3"
    assert trigger_fn("how are you") is None


def test_app_open_and_file_open_have_verbatim_response_flag():
    skills = load_skills()
    by_id = {s.id: s for s in skills}
    assert by_id["app_open"].flags.get("verbatim_response") is True
    assert by_id["file_open"].flags.get("verbatim_response") is True
    # No other skill should have it set.
    for skill in skills:
        if skill.id not in ("app_open", "file_open"):
            assert not skill.flags.get("verbatim_response")


def test_requires_grounding_flag_set_on_calculate_and_datetime_only():
    """
    calculate and datetime both need the LLM to narrate a real computed fact
    rather than guess — arithmetic and the current date/time respectively.
    No other skill should set this flag.
    """
    skills = load_skills()
    for skill in skills:
        expected = skill.id in ("calculate", "datetime")
        assert bool(skill.flags.get("requires_grounding")) == expected


def test_malformed_skill_file_raises_loudly(tmp_path):
    """A broken SKILL.md must fail LOUD at load time, never be silently skipped."""
    bad_file = tmp_path / "broken.SKILL.md"
    bad_file.write_text("this has no frontmatter delimiters at all", encoding="utf-8")

    with pytest.raises(ValueError):
        load_skills(skills_dir=tmp_path)


def test_skill_missing_required_field_raises(tmp_path):
    bad_file = tmp_path / "broken.SKILL.md"
    bad_file.write_text(
        "---\nid: broken\nname: Broken\ntype: intent\npriority: 5\n"
        "handler: os:getcwd\npatterns: {}\n---\nbody\n",
        encoding="utf-8",
    )  # missing 'description'

    with pytest.raises(ValueError):
        load_skills(skills_dir=tmp_path)


# ── mode_switch skill ─────────────────────────────────────────────────────────

def test_mode_switch_skill_loads_all_31_entries_in_original_order():
    ms = load_mode_switch_skill()
    assert ms.type == "mode_switch"
    assert len(ms.mode_patterns) == 31

    # Spot-check first, a middle multilingual, and last entries against the
    # exact original _MODE_SWITCH_PATTERNS tuple list from api/routes/chat.py.
    assert ms.mode_patterns[0] == (
        r"\b(switch|change|go|put|set)\s+(to\s+)?(casual|chill|relax(ed)?|friendly|informal)\b",
        "casual",
    )
    assert ms.mode_patterns[-2] == (r"\bغير\s+رسمي\b", "casual")
    assert ms.mode_patterns[-1] == (r"\bرسمي\b", "professional")
    assert (r"\bkasual\b", "casual") in ms.mode_patterns
    assert (r"\bzhuānyè\b", "professional") in ms.mode_patterns


def test_mode_switch_pattern_target_counts():
    ms = load_mode_switch_skill()
    casual_count = sum(1 for _, target in ms.mode_patterns if target == "casual")
    professional_count = sum(1 for _, target in ms.mode_patterns if target == "professional")
    assert casual_count == 17
    assert professional_count == 14


# ── Integration with core/agent.py's dynamic app_open pattern append ─────────

def test_app_open_skill_gains_dynamic_app_name_patterns_via_agent_import():
    """
    skills/app_open.SKILL.md's OWN static patterns list only has 2 entries
    (\\blaunch\\b, \\bstart\\b...) — core/agent.py appends 4 more, built from
    the live tools.app_control.APP_MAP, at import time. Importing core.agent
    must mutate the SAME Skill object load_skills() would otherwise return
    with only the static patterns.
    """
    import core.agent  # noqa: F401 — import triggers the dynamic append

    skill = core.agent._SKILLS_BY_ID["app_open"]
    assert len(skill.patterns) == 2 + 4  # 2 static (YAML) + 4 dynamic (APP_MAP-derived)
