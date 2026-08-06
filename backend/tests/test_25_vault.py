"""
test_25_vault.py — Tests for core/vault.py, the persistent Obsidian-compatible
markdown memory vault (durable cross-session layer, distinct from
core/memory.py's session-only in-process dict).

Every test here uses its own isolated `Vault(root=tmp_path)` instance — the
autouse `_isolated_vault` fixture in conftest.py already repoints the
module-level `vault` singleton at a tmp dir for the whole suite, but these
tests want fine-grained control over the root, so they construct their own.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

from core.vault import Vault


# ── Raw capture ────────────────────────────────────────────────────────────────

def test_raw_file_created_per_turn(tmp_path):
    v = Vault(root=tmp_path)
    full_session_id = "sess-00011234"
    v.record_turn(
        session_id=full_session_id,
        user_message="Hello there",
        user_language="en",
        assistant_response="Greetings, sir.",
        mode="professional",
        intent="direct_answer",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    raw_file = tmp_path / "raw" / f"{today}.md"
    assert raw_file.exists()

    content = raw_file.read_text(encoding="utf-8")
    assert f"# {today}" in content
    assert f"Session `{full_session_id[:8]}`" in content
    assert "**User** (en): Hello there" in content
    assert "**Ultron** (professional): Greetings, sir." in content
    assert "*Intent: direct_answer*" in content


def test_raw_capture_one_file_per_day_not_per_session(tmp_path):
    """Two different sessions on the same day append to the SAME daily file."""
    v = Vault(root=tmp_path)
    v.record_turn("sess-A", "msg A", "en", "resp A", "professional")
    v.record_turn("sess-B", "msg B", "en", "resp B", "casual")

    today = datetime.now().strftime("%Y-%m-%d")
    raw_files = list((tmp_path / "raw").glob("*.md"))
    assert len(raw_files) == 1
    assert raw_files[0].name == f"{today}.md"

    content = raw_files[0].read_text(encoding="utf-8")
    assert "sess-A" in content and "sess-B" in content
    # Header written only once, at the top of the file
    assert content.count(f"# {today}") == 1


def test_record_turn_never_raises_on_unwritable_root(tmp_path):
    """A blocked/unwritable root must never propagate an exception to the caller."""
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("i am a file, not a directory")
    v = Vault(root=blocked / "nested")  # mkdir(parents=True) under a file must fail

    # Must not raise.
    v.record_turn("sess-X", "hi", "en", "hello", "professional")


# ── Wiki layer / entity extraction ──────────────────────────────────────────────

def test_wiki_note_created_for_notable_entity(tmp_path):
    v = Vault(root=tmp_path)
    full_session_id = "sess-000212345"
    v.record_turn(
        session_id=full_session_id,
        user_message="Tell me about OweWise progress",
        user_language="en",
        assistant_response="OweWise is on track, sir.",
        mode="professional",
        intent="direct_answer",
    )

    wiki_file = tmp_path / "wiki" / "OweWise.md"
    assert wiki_file.exists()
    content = wiki_file.read_text(encoding="utf-8")
    assert content.startswith("# OweWise")
    assert "## Mentions" in content
    assert full_session_id[:8] in content


def test_raw_and_wiki_notes_cross_link(tmp_path):
    v = Vault(root=tmp_path)
    v.record_turn(
        session_id="sess-0003",
        user_message="What about OweWise?",
        user_language="en",
        assistant_response="OweWise is fine.",
        mode="professional",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    raw_content = (tmp_path / "raw" / f"{today}.md").read_text(encoding="utf-8")
    wiki_content = (tmp_path / "wiki" / "OweWise.md").read_text(encoding="utf-8")

    assert "[[OweWise]]" in raw_content          # raw -> wiki
    assert f"[[{today}]]" in wiki_content         # wiki -> raw (daily note)


def test_entity_extraction_filters_sentence_initial_words(tmp_path):
    """
    Ordinary capitalized sentence-starters (English or otherwise) must not
    become spurious wiki notes — only genuine mid-sentence proper nouns
    (or multi-word Title-Case phrases) qualify. Regression case: Spanish
    "Hola, ..." / "Todo bien..." previously created bogus "Hola"/"Todo" notes.
    """
    v = Vault(root=tmp_path)
    v.record_turn(
        session_id="sess-es",
        user_message="Hola, ¿qué tal, OweWise?",
        user_language="es",
        assistant_response="Todo bien, sir. OweWise está funcionando correctamente.",
        mode="professional",
    )

    wiki_names = {p.stem for p in (tmp_path / "wiki").glob("*.md")}
    assert wiki_names == {"OweWise"}


def test_entity_extraction_keeps_multiword_titlecase_phrase(tmp_path):
    v = Vault(root=tmp_path)
    entities = v._extract_entities("I am planning a trip to New York next week.")
    assert "New York" in entities


def test_entity_extraction_strips_leading_article_not_whole_phrase(tmp_path):
    """
    Regression: "The OweWise project is on track" must extract "OweWise",
    not a separate bogus "The OweWise" note alongside the correct one —
    caught via a real live vault write during this feature's own development
    (a sentence starting with "The <Entity>" produced a duplicate note).
    """
    v = Vault(root=tmp_path)
    entities = v._extract_entities("The OweWise project is on track.")
    assert entities == ["OweWise"]


def test_entity_extraction_leading_word_strip_does_not_bypass_stopword_check(tmp_path):
    """
    Regression: caught via a real live /chat call against the running
    backend — "Hello Ultron, what is your status?" produced a bogus
    wiki/Ultron.md note. "Hello Ultron" matches as one multi-word candidate,
    strips to "Ultron" (itself in the stopword list, deliberately, so the AI
    doesn't clutter its own wiki with self-references) — the leading-word
    strip must not let the remainder skip the stopword check just because
    stripping happened.
    """
    v = Vault(root=tmp_path)
    assert v._extract_entities("Hello Ultron, what is your status?") == []


# ── Real FIFA World Cup conversation regressions (caught via live usage) ────────

def test_fifa_conversation_yet_not_extracted_united_states_has_space(tmp_path):
    """
    Regression, caught live in Obsidian after a real conversation: a
    standalone italicized "*Yet.*" fragment was extracted as junk entity
    "Yet", and "United States" got an underscored filename
    ("United_States.md") while its wikilink text/title kept a real space —
    a genuine mismatch that made the wikilink unresolved in Obsidian.
    """
    v = Vault(root=tmp_path)
    text = (
        "Sir, the World Cup will be held in the United States, Canada, "
        "and Mexico. *Yet.*"
    )
    entities = v._extract_entities(text)

    assert "Yet" not in entities
    assert "United States" in entities
    assert "United_States" not in entities  # must never appear underscored
    assert "Canada" in entities
    assert "Mexico" in entities

    # Filename must match the entity text exactly — no underscore substitution.
    assert v._safe_filename("United States") == "United States"


@pytest.mark.parametrize("text", [
    "But that's not all.",
    "So there's that.",
    "However, that's not confirmed.",
    "Still, it's worth noting.",
    "Actually, that's incorrect.",
])
def test_sentence_starter_fragments_produce_no_junk_entities(text, tmp_path):
    v = Vault(root=tmp_path)
    assert v._extract_entities(text) == []


def test_markdown_emphasis_stripped_before_entity_matching(tmp_path):
    """
    "*Yet.*" — the asterisks must not defeat the sentence-initial check by
    sitting between the real sentence boundary and the word. A bolded word
    genuinely mid-sentence ("**Canada**") must still be extracted normally —
    markdown-stripping must not suppress real entities, only unmask the
    sentence-boundary signal markdown was hiding.
    """
    v = Vault(root=tmp_path)
    assert v._extract_entities("Not a time traveler. *Yet.*") == []
    assert v._extract_entities("This news is about **Canada** today.") == ["Canada"]


def test_wiki_note_filenames_use_spaces_not_underscores_end_to_end(tmp_path):
    """Full record_turn() path: the wiki note for a multi-word entity must
    be a real file with spaces in its name, not underscores."""
    v = Vault(root=tmp_path)
    v.record_turn(
        session_id="fifa-test",
        user_message="who won fifa 2026",
        user_language="en",
        assistant_response=(
            "Sir, the 2026 FIFA World Cup has not yet been played. It is "
            "scheduled to be held across the United States, Canada, and "
            "Mexico in the summer of 2026.\n\n"
            "I am many things, but a time traveler is not one of them. *Yet.*"
        ),
        mode="professional",
    )

    wiki_files = {p.name for p in (tmp_path / "wiki").glob("*.md")}
    assert wiki_files == {
        "FIFA World Cup.md", "United States.md", "Canada.md", "Mexico.md",
    }
    assert "Yet.md" not in wiki_files
    assert "United_States.md" not in wiki_files
    assert "FIFA_World_Cup.md" not in wiki_files


def test_wiki_note_dedupes_identical_mentions(tmp_path):
    """Two identical mentions at the exact same timestamp must not duplicate the line."""
    v = Vault(root=tmp_path)
    v._ensure_dirs()
    fixed_now = datetime(2026, 1, 1, 12, 0, 0)
    v._upsert_wiki_note(entity="Foo", now=fixed_now, session_id="s1", mode="professional", excerpt="hi")
    v._upsert_wiki_note(entity="Foo", now=fixed_now, session_id="s1", mode="professional", excerpt="hi")

    content = (tmp_path / "wiki" / "Foo.md").read_text(encoding="utf-8")
    assert content.count("session `s1`") == 1


# ── Cross-session recall ─────────────────────────────────────────────────────────

def test_cross_session_recall_retrieves_relevant_context(tmp_path):
    """A fresh Vault instance (simulating a new session/backend restart) must be
    able to recall context written by a prior instance pointed at the same root."""
    v1 = Vault(root=tmp_path)
    v1.record_turn(
        session_id="sess-old",
        user_message="The OweWise deadline is next Friday",
        user_language="en",
        assistant_response="Noted, sir — the OweWise deadline is next Friday.",
        mode="professional",
    )

    v2 = Vault(root=tmp_path)  # simulates a brand new session / fresh process
    context = v2.get_context_for_query("What's the status on OweWise?")
    assert context != ""
    assert "OweWise" in context


def test_get_context_for_query_no_match_returns_empty(tmp_path):
    v = Vault(root=tmp_path)
    v.record_turn("sess-1", "OweWise update", "en", "OweWise is fine.", "professional")
    assert v.get_context_for_query("completely unrelated topic here") == ""


def test_get_context_for_query_empty_vault_returns_empty(tmp_path):
    v = Vault(root=tmp_path)
    assert v.get_context_for_query("anything at all") == ""


def test_get_context_for_query_only_scans_wiki_not_raw(tmp_path):
    """
    Scoped lookup requirement: get_context_for_query() must match against
    wiki/ note titles, not do a full-text scan of raw/ — a word that only
    appears in raw conversation text (never promoted to a wiki note) must
    not surface as a match.
    """
    v = Vault(root=tmp_path)
    v.record_turn(
        "sess-1",
        "just chatting about ordinary things",
        "en",
        "ordinary things indeed, sir",
        "professional",
    )
    # "ordinary" appears in raw/ but never became a wiki note (lowercase, no
    # Title-Case proper-noun signal) -> must not match.
    assert v.get_context_for_query("tell me about ordinary things") == ""


# ── Markdown validity ─────────────────────────────────────────────────────────────

def test_vault_files_are_valid_markdown(tmp_path):
    v = Vault(root=tmp_path)
    v.record_turn(
        "sess-md", "Ask about OweWise", "en", "OweWise is fine, sir.", "professional",
    )

    today = datetime.now().strftime("%Y-%m-%d")
    raw_content = (tmp_path / "raw" / f"{today}.md").read_text(encoding="utf-8")
    wiki_content = (tmp_path / "wiki" / "OweWise.md").read_text(encoding="utf-8")

    for content in (raw_content, wiki_content):
        assert content.startswith("# ")
        assert "## " in content
        # No unclosed wikilink brackets
        assert content.count("[[") == content.count("]]")


# ── Gitignore verification (real repo, not the .gitignore file's own text) ──────

def test_vault_directory_is_really_gitignored():
    """
    Verifies via `git check-ignore` against the actual repo that
    backend/vault/ is genuinely excluded — not just that the .gitignore
    file happens to contain the string "vault" somewhere.
    """
    repo_root = Path(__file__).parent.parent.parent  # backend/tests -> backend -> repo root
    result = subprocess.run(
        ["git", "check-ignore", "-q", "backend/vault/raw/some_real_conversation.md"],
        cwd=str(repo_root),
        capture_output=True,
    )
    assert result.returncode == 0, (
        "backend/vault/ is NOT gitignored — real personal conversation data "
        "could be committed. git check-ignore exit code: "
        f"{result.returncode}, stderr: {result.stderr!r}"
    )
