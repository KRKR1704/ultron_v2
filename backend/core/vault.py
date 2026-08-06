"""
core/vault.py — Persistent, Obsidian-compatible markdown memory vault.

This is the DURABLE cross-session memory layer, distinct from core/memory.py's
ConversationMemory (a fast, in-process dict that dies on restart and only
covers the current session). vault.py writes real markdown files to disk:

  vault/raw/YYYY-MM-DD.md   — every conversation turn, one file per day
  vault/wiki/<Entity>.md    — distilled notes on recurring topics/entities,
                               cross-linked with real Obsidian [[wikilinks]]
  vault/outputs/            — reserved for generated content (search
                               summaries, calendar digests, ...); not written
                               to by this module today, wired up incrementally

Entity extraction is a deliberately pragmatic regex heuristic (Title-Case
proper-noun detection), not an NLP pipeline or an LLM side-call — see
_extract_entities() docstring for why.

Entity extraction runs over BOTH sides of a turn — the user's message AND
Ultron's own response (see record_turn()) — by design, not as an accidental
side effect. Ultron's responses usually carry the actual substantive facts
worth remembering (e.g. "the World Cup will be held in the United States,
Canada, and Mexico" is Ultron's answer, not the user's question), so
scanning only the user's side would miss most of what's actually worth
cross-linking.
"""

import logging
import re
import time
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

log = logging.getLogger(__name__)

_DEFAULT_ROOT = Path(__file__).parent.parent / "vault"

# ── Entity extraction ──────────────────────────────────────────────────────────
# Title-Case word sequences (1-3 words) — a plain proper-noun heuristic. This
# only fires on Latin-script text (Title-Case has no meaning in Devanagari/
# CJK/Arabic scripts) — an accepted, documented limitation of staying
# pragmatic rather than building real per-language NLP here.
# NOTE: continuation whitespace is [ \t]+, NOT \s+ — deliberately excludes
# newlines so a multi-word match can never bridge across lines (relevant
# because entity extraction runs per-segment on possibly multi-line messages).
_ENTITY_PATTERN = re.compile(r"\b[A-Z][a-zA-Z0-9]*(?:[ \t]+[A-Z][a-zA-Z0-9]*){0,2}\b")

# Common sentence-starters / pronouns / temporal words that would otherwise be
# mistaken for proper nouns purely because they're capitalized at the start of
# a sentence. Only applied to SINGLE-word candidates — a multi-word Title-Case
# phrase ("New York", "Owe Wise") is essentially never one of these.
_ENTITY_STOPWORDS = {
    "i", "the", "a", "an", "this", "that", "these", "those", "you", "your",
    "yours", "we", "our", "he", "she", "it", "they", "them", "their",
    "sir", "ultron", "hello", "hi", "hey", "yes", "no", "okay", "ok",
    "what", "when", "where", "why", "how", "who", "which", "whose",
    "please", "thanks", "thank", "sorry", "today", "tomorrow", "yesterday",
    "now", "here", "there", "well", "so", "and", "but", "or", "if",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    # Discourse markers / sentence adverbs — real, caught live: a standalone
    # italicized fragment "*Yet.*" got extracted as entity "Yet". These are
    # words that are near-never proper nouns regardless of WHERE they sit in
    # a sentence, so they're listed explicitly rather than relied on only
    # via the sentence-initial-position check (defense in depth — that check
    # can be defeated by markdown formatting sitting between the real
    # sentence boundary and the word, as "*Yet.*" was, see
    # _strip_markdown_emphasis() below for the other half of that fix).
    "yet", "however", "also", "still", "actually", "meanwhile", "anyway",
    "anyhow", "indeed", "perhaps", "maybe", "certainly", "clearly",
    "obviously", "basically", "essentially", "furthermore", "moreover",
    "nevertheless", "nonetheless", "regardless", "finally", "instead",
    "otherwise", "additionally", "consequently", "therefore", "thus",
    "hence", "overall", "undoubtedly", "naturally", "surely", "truly",
    "honestly", "frankly", "unfortunately", "fortunately", "interestingly",
    "importantly", "notably", "specifically", "ultimately", "eventually",
    "initially", "subsequently", "previously", "currently", "recently",
    "presently", "immediately", "suddenly", "gradually", "simultaneously",
    "alright",
}

_MAX_ENTITIES_PER_TURN = 5

# Markdown emphasis/formatting markers (*italic*, **bold**, _italic_,
# `code`) — neutralized (replaced with a space, not deleted, so character
# offsets stay aligned with the original text for the sentence-initial
# check) before entity matching. Without this, a standalone emphasized
# fragment like "*Yet.*" has "*" sitting between the real sentence boundary
# and the word — "*" isn't whitespace or a sentence terminator, so the
# position-based sentence-initial check couldn't tell it apart from a
# genuine mid-sentence word.
_MARKDOWN_EMPHASIS = re.compile(r"[*_`]+")


class Vault:
    """
    Durable, Obsidian-compatible markdown memory vault.

    A class (not bare module functions) so tests can instantiate an isolated
    instance (Vault(root=tmp_path)) instead of touching the real vault —
    mirrors core.memory.ConversationMemory's class-based pattern.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = root or _DEFAULT_ROOT
        self.raw_dir = self.root / "raw"
        self.wiki_dir = self.root / "wiki"
        self.outputs_dir = self.root / "outputs"
        self._lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    def record_turn(
        self,
        session_id: str,
        user_message: str,
        user_language: str,
        assistant_response: str,
        mode: str,
        intent: Optional[str] = None,
    ) -> None:
        """
        Append one conversation turn to today's raw daily note, then extract
        and cross-link any notable entities. Never raises — a vault write
        failure must never break a chat response; callers wrap this, but it
        also guards itself so direct callers/tests get the same guarantee.
        """
        try:
            self._ensure_dirs()
            now = datetime.now()
            # Extracted per-segment, not on a joined "user\nassistant" string —
            # \s+ matches newlines too, so a naive join lets a multi-word
            # Title-Case match bridge across the user/assistant boundary
            # (e.g. "...next Friday" + "Noted, sir..." -> bogus "Friday\nNoted").
            entities = self._merge_entities(
                self._extract_entities(user_message),
                self._extract_entities(assistant_response),
            )

            with self._lock:
                self._append_raw(
                    now=now,
                    session_id=session_id,
                    user_message=user_message,
                    user_language=user_language,
                    assistant_response=assistant_response,
                    mode=mode,
                    intent=intent,
                    entities=entities,
                )
                for entity in entities:
                    self._upsert_wiki_note(
                        entity=entity,
                        now=now,
                        session_id=session_id,
                        mode=mode,
                        excerpt=user_message,
                    )
        except Exception as err:
            log.warning("Vault record_turn failed (non-fatal): %s", err)

    def get_context_for_query(
        self,
        text: str,
        max_notes: int = 3,
        max_chars_per_note: int = 800,
    ) -> str:
        """
        Cheap, scoped cross-session recall: list wiki/ note filenames (NOT a
        full-text scan of raw/) and check simple case-insensitive substring
        containment of each entity name against *text*. Returns a formatted
        context block for up to *max_notes* matches, or "" if nothing
        matches / the vault is empty — so callers never inject empty noise
        into a prompt and pay near-zero cost on a cold vault.
        """
        try:
            if not self.wiki_dir.exists():
                return ""

            lower_text = text.lower()
            matches: list[Path] = []
            for note_path in sorted(self.wiki_dir.glob("*.md")):
                # Filenames keep real spaces now (see _safe_filename), so
                # this is a no-op for current notes — kept only as a
                # backward-compat shim for any pre-fix underscored filename
                # that might still be lying around.
                entity = note_path.stem.replace("_", " ")
                if entity.lower() in lower_text:
                    matches.append(note_path)
                if len(matches) >= max_notes:
                    break

            if not matches:
                return ""

            blocks = []
            for note_path in matches:
                content = note_path.read_text(encoding="utf-8")[:max_chars_per_note]
                blocks.append(f"## {note_path.stem}\n{content}")

            return "Relevant background from prior sessions:\n\n" + "\n\n".join(blocks)
        except Exception as err:
            log.warning("Vault get_context_for_query failed (non-fatal): %s", err)
            return ""

    # ── Internal: raw capture ────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        for d in (self.raw_dir, self.wiki_dir, self.outputs_dir):
            d.mkdir(parents=True, exist_ok=True)

    def _daily_note_path(self, now: datetime) -> Path:
        return self.raw_dir / f"{now.strftime('%Y-%m-%d')}.md"

    def _append_raw(
        self,
        now: datetime,
        session_id: str,
        user_message: str,
        user_language: str,
        assistant_response: str,
        mode: str,
        intent: Optional[str],
        entities: list[str],
    ) -> None:
        path = self._daily_note_path(now)
        is_new = not path.exists()

        lines: list[str] = []
        if is_new:
            lines.append(f"# {now.strftime('%Y-%m-%d')}")
            lines.append("")

        session_short = session_id[:8] if session_id else "unknown"
        lines.append(f"## {now.strftime('%H:%M:%S')} — Session `{session_short}`")
        lines.append("")
        lines.append(f"**User** ({user_language}): {user_message}")
        lines.append("")
        lines.append(f"**Ultron** ({mode}): {assistant_response}")
        lines.append("")
        if intent:
            lines.append(f"*Intent: {intent}*")
        if entities:
            related = ", ".join(f"[[{e}]]" for e in entities)
            lines.append(f"Related: {related}")
        lines.append("")
        lines.append("---")
        lines.append("")

        with open(path, "a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    # ── Internal: entity extraction + wiki upsert ───────────────────────────

    def _extract_entities(self, text: str) -> list[str]:
        """
        Pragmatic proper-noun heuristic: Title-Case word sequences (1-3
        words), deduped, capped at _MAX_ENTITIES_PER_TURN. Not real NLP —
        deliberately simple, deterministic, and fast (no network/LLM call),
        per the project's explicit "don't over-engineer this" guidance.

        Three filters keep ordinary capitalization from flooding the wiki:
          - markdown emphasis markers (*, _, `) are neutralized first (see
            _MARKDOWN_EMPHASIS) — a standalone "*Yet.*" fragment would
            otherwise defeat the sentence-initial check below, since "*"
            isn't whitespace or a sentence terminator;
          - stopword-list words are dropped (catches "I", "The", "Sir",
            discourse markers like "Yet"/"However"/"Still", ...) —
            including as the LEADING word of a multi-word match, which is
            stripped rather than discarding the whole match (a sentence like
            "The OweWise project..." must resolve to the entity "OweWise",
            not a separate bogus "The OweWise" note alongside it);
          - single-word candidates sitting at the START of a sentence are
            also dropped UNLESS multi-word (this is what actually matters
            for non-English text: "Hola, ..." and "Todo bien..." are just
            ordinary sentence-initial capitalization in Spanish, not proper
            nouns — there's no stopword list broad enough to cover every
            language, so position is the more reliable signal there).
        Multi-word Title-Case phrases ("New York", "Owe Wise") are otherwise
        kept regardless of position — accidental multi-word capitalization
        at a sentence boundary is rare enough not to bother filtering.

        Deliberately NOT doing a dictionary-word lookup (e.g. rejecting any
        single common English word even outside the stopword list): that
        would need a bundled wordlist dependency for marginal extra
        precision over the markdown-stripping + expanded-stopword-list +
        position-check combination above, which is real over-engineering
        for what's meant to stay a pragmatic heuristic, not an NLP pipeline.
        """
        text = _MARKDOWN_EMPHASIS.sub(" ", text)

        seen: list[str] = []
        for match in _ENTITY_PATTERN.finditer(text):
            candidate = match.group(0).strip()

            # Strip a leading stopword from a multi-word match ("The OweWise"
            # -> "OweWise") instead of discarding the whole thing. A word
            # immediately following a stripped article/pronoun ("The X",
            # "This X") is a strong signal X is a real noun phrase, not raw
            # sentence-initial capitalization noise — so once we've stripped
            # something, the remainder is exempt from the sentence-initial
            # check below (it no longer IS sentence-initial; "The" was).
            words = candidate.split(" ")
            stripped_any = False
            while len(words) > 1 and words[0].lower() in _ENTITY_STOPWORDS:
                words = words[1:]
                stripped_any = True
            candidate = " ".join(words)

            if len(candidate) < 3:
                continue

            is_multi_word = " " in candidate
            if not is_multi_word:
                # The stopword check must run regardless of stripped_any —
                # "Hello Ultron" strips to "Ultron", which is ITSELF a
                # stopword (Ultron's own name is deliberately excluded so
                # the AI doesn't clutter its own wiki with self-references)
                # and must still be caught here, not just words that were
                # never part of a multi-word match.
                if candidate.lower() in _ENTITY_STOPWORDS:
                    continue
                # Only the sentence-initial check is skipped after a strip —
                # a word right after a stripped article ("The X") is not
                # actually sentence-initial anymore, "The" was.
                if not stripped_any and self._is_sentence_initial(text, match.start()):
                    continue

            if candidate not in seen:
                seen.append(candidate)
            if len(seen) >= _MAX_ENTITIES_PER_TURN:
                break
        return seen

    @staticmethod
    def _merge_entities(*entity_lists: list[str]) -> list[str]:
        """Dedupe and cap across multiple per-segment entity extractions."""
        merged: list[str] = []
        for entities in entity_lists:
            for entity in entities:
                if entity not in merged:
                    merged.append(entity)
                if len(merged) >= _MAX_ENTITIES_PER_TURN:
                    return merged
        return merged

    @staticmethod
    def _is_sentence_initial(text: str, match_start: int) -> bool:
        """True if nothing but whitespace/sentence-terminators precede the
        match on its line — i.e. it's the first word of a sentence, not a
        genuine mid-sentence proper noun."""
        preceding = text[:match_start].rstrip()
        if not preceding:
            return True
        return preceding[-1] in ".!?¿¡\n"

    def _safe_filename(self, entity: str) -> str:
        """
        Sanitize an entity name into a Windows-safe filename stem.

        Deliberately keeps real spaces — NTFS/Windows filenames handle
        spaces fine, and the filename is what Obsidian resolves [[wikilinks]]
        against. A prior version replaced spaces with underscores here,
        which meant "United States" got a title of "United States" (the raw
        entity, used for the `#` heading and every wikilink) but a filename
        of "United_States.md" — a real mismatch caught live via Obsidian:
        `[[United States]]` never resolves to a file literally named
        `United_States.md`, so it showed as an unresolved/phantom graph
        node while the real (oddly-underscored) file sat unlinked next to
        it. Only characters Windows genuinely disallows in filenames are
        stripped; spaces are left untouched so filename == title ==
        wikilink text everywhere, consistently.
        """
        cleaned = re.sub(r'[<>:"/\\|?*]', "", entity).strip()
        return cleaned or "Unknown"

    def _upsert_wiki_note(
        self,
        entity: str,
        now: datetime,
        session_id: str,
        mode: str,
        excerpt: str,
    ) -> None:
        filename = self._safe_filename(entity)
        path = self.wiki_dir / f"{filename}.md"
        session_short = session_id[:8] if session_id else "unknown"
        short_excerpt = excerpt.strip().replace("\n", " ")
        if len(short_excerpt) > 120:
            short_excerpt = short_excerpt[:117] + "..."

        daily_note_stem = now.strftime("%Y-%m-%d")
        mention_line = (
            f"- **{now.strftime('%Y-%m-%d %H:%M')}** (session `{session_short}`) — "
            f"mode: {mode} — \"{short_excerpt}\" → [[{daily_note_stem}]]"
        )

        if not path.exists():
            content = (
                f"# {entity}\n\n"
                "*Auto-tracked by ULTRON's memory vault.*\n\n"
                "## Mentions\n\n"
                f"{mention_line}\n"
            )
            path.write_text(content, encoding="utf-8")
            return

        existing = path.read_text(encoding="utf-8")
        if mention_line in existing:
            return  # avoid unbounded duplicate growth on identical repeats
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{mention_line}\n")


# ── Module-level singleton ────────────────────────────────────────────────────
# Imported and used throughout the backend. Tests repoint this via an autouse
# conftest.py fixture so the real backend/vault/ directory is never touched by
# the test suite.
vault = Vault()
