"""
skills/loader.py — Parses backend/skills/*.SKILL.md into Skill objects.

This is config-driven regex-matching, NOT a real agent framework — the
matching MECHANISM is unchanged from core/agent.py's original hardcoded
`_INTENT_PATTERNS` (plain `re.search` per pattern, first match wins). What's
new is that the pattern data now lives in versionable, human-readable
markdown files instead of Python literals, so adding a trigger phrase (or an
entirely new skill) means adding/editing a `*.SKILL.md` file — no
core/agent.py code changes required.

See skills/README.md for the full file-format reference.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

log = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent
_FRONTMATTER_DELIM = "---"


@dataclass
class Skill:
    id: str
    name: str
    description: str
    type: str                      # "intent" | "mode_switch"
    trigger_type: str              # "regex" | "function" | "" (mode_switch)
    priority: int
    handler: Optional[str]         # "module.path:function_name"
    flags: dict[str, Any] = field(default_factory=dict)
    patterns: list[str] = field(default_factory=list)          # intent, trigger_type=regex
    trigger_fn_ref: Optional[str] = None                       # intent, trigger_type=function
    mode_patterns: list[tuple[str, str]] = field(default_factory=list)  # mode_switch only
    data: dict[str, Any] = field(default_factory=dict)         # extra frontmatter (e.g. foreign_aliases)
    source_path: Optional[Path] = None

    _handler_cache: Optional[Callable] = field(default=None, repr=False, compare=False)
    _trigger_fn_cache: Optional[Callable] = field(default=None, repr=False, compare=False)

    def resolve_handler(self) -> Callable:
        if self._handler_cache is None:
            self._handler_cache = _resolve_ref(self.handler)
        return self._handler_cache

    def resolve_trigger_fn(self) -> Callable:
        if self._trigger_fn_cache is None:
            self._trigger_fn_cache = _resolve_ref(self.trigger_fn_ref)
        return self._trigger_fn_cache


def _resolve_ref(ref: Optional[str]) -> Callable:
    """Resolve a 'module.path:function_name' string to a real callable."""
    if not ref or ":" not in ref:
        raise ValueError(f"Invalid handler/trigger_fn reference: {ref!r}")
    module_path, func_name = ref.split(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)


def _parse_frontmatter(path: Path) -> dict[str, Any]:
    """Split a SKILL.md file on '---' delimiters and YAML-parse the frontmatter block."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    if not lines or lines[0].strip() != _FRONTMATTER_DELIM:
        raise ValueError(f"{path.name}: missing frontmatter opening '---'")

    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == _FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        raise ValueError(f"{path.name}: missing frontmatter closing '---'")

    frontmatter_text = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as err:
        raise ValueError(f"{path.name}: invalid YAML frontmatter: {err}") from err

    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: frontmatter must be a YAML mapping")
    return data


def _flatten_patterns(patterns_field: Any, source_name: str) -> list[str]:
    """
    patterns: is a dict of {group_name: [pattern, ...]} for intent/regex
    skills — grouping is purely documentation (which language(s) a group
    targets), matching is a flat any-match over every pattern regardless of
    group. An empty/missing patterns field (e.g. the `calculate` skill,
    trigger_type=function) flattens to [].
    """
    if not patterns_field:
        return []
    if not isinstance(patterns_field, dict):
        raise ValueError(f"{source_name}: 'patterns' must be a mapping of group -> [patterns]")

    flat: list[str] = []
    for group_name, group_patterns in patterns_field.items():
        if not isinstance(group_patterns, list):
            raise ValueError(
                f"{source_name}: patterns.{group_name} must be a list of pattern strings"
            )
        flat.extend(group_patterns)
    return flat


def _parse_mode_patterns(patterns_field: Any, source_name: str) -> list[tuple[str, str]]:
    """
    mode_switch skills use a single ORDERED list of {pattern, target} entries
    (not grouped by target) — this reproduces chat.py's original
    _MODE_SWITCH_PATTERNS tuple-list order exactly, which matters because
    matching is first-match-wins across the whole list.
    """
    if not isinstance(patterns_field, list):
        raise ValueError(f"{source_name}: mode_switch 'patterns' must be a list of {{pattern, target}}")

    result = []
    for entry in patterns_field:
        if not isinstance(entry, dict) or "pattern" not in entry or "target" not in entry:
            raise ValueError(f"{source_name}: each mode_switch pattern entry needs 'pattern' and 'target'")
        result.append((entry["pattern"], entry["target"]))
    return result


def _build_skill(raw: dict[str, Any], path: Path) -> Skill:
    required = ("id", "name", "description", "type")
    for key in required:
        if key not in raw:
            raise ValueError(f"{path.name}: missing required frontmatter field '{key}'")

    skill_type = raw["type"]
    known_keys = {
        "id", "name", "description", "type", "trigger_type", "priority",
        "handler", "flags", "patterns", "trigger_fn",
    }
    extra_data = {k: v for k, v in raw.items() if k not in known_keys}

    if skill_type == "mode_switch":
        return Skill(
            id=raw["id"],
            name=raw["name"],
            description=raw["description"],
            type=skill_type,
            trigger_type="regex",
            priority=int(raw.get("priority", 0)),
            handler=raw.get("handler"),
            flags=raw.get("flags", {}) or {},
            mode_patterns=_parse_mode_patterns(raw.get("patterns", []), path.name),
            data=extra_data,
            source_path=path,
        )

    if skill_type == "intent":
        trigger_type = raw.get("trigger_type", "regex")
        if "priority" not in raw:
            raise ValueError(f"{path.name}: intent skills require an explicit 'priority'")

        trigger_fn_ref = raw.get("trigger_fn")
        if trigger_type == "function" and not trigger_fn_ref:
            raise ValueError(f"{path.name}: trigger_type=function requires 'trigger_fn'")

        if not raw.get("handler"):
            raise ValueError(f"{path.name}: intent skills require a 'handler'")

        return Skill(
            id=raw["id"],
            name=raw["name"],
            description=raw["description"],
            type=skill_type,
            trigger_type=trigger_type,
            priority=int(raw["priority"]),
            handler=raw["handler"],
            flags=raw.get("flags", {}) or {},
            patterns=_flatten_patterns(raw.get("patterns"), path.name),
            trigger_fn_ref=trigger_fn_ref,
            data=extra_data,
            source_path=path,
        )

    raise ValueError(f"{path.name}: unknown skill type {skill_type!r} (expected 'intent' or 'mode_switch')")


def load_skills(skills_dir: Optional[Path] = None) -> list[Skill]:
    """
    Parse every *.SKILL.md file in *skills_dir* (default: backend/skills/).
    Returns `type: intent` skills only, sorted by priority ascending — this
    reproduces the exact order core/agent.py's original hardcoded
    _INTENT_PATTERNS list relied on for first-match-wins classification.

    Fails LOUD (raises) on any malformed skill file rather than silently
    skipping it — a silently-dropped skill is exactly the kind of regression
    this system exists to prevent.
    """
    d = skills_dir or _SKILLS_DIR
    skills: list[Skill] = []
    for path in sorted(d.glob("*.SKILL.md")):
        raw = _parse_frontmatter(path)
        skill = _build_skill(raw, path)
        if skill.type == "intent":
            skills.append(skill)

    skills.sort(key=lambda s: s.priority)
    return skills


def load_mode_switch_skill(skills_dir: Optional[Path] = None) -> Skill:
    """Load the single `type: mode_switch` skill (used by api/routes/chat.py)."""
    d = skills_dir or _SKILLS_DIR
    for path in sorted(d.glob("*.SKILL.md")):
        raw = _parse_frontmatter(path)
        if raw.get("type") == "mode_switch":
            return _build_skill(raw, path)
    raise FileNotFoundError(f"No type: mode_switch SKILL.md found under {d}")
