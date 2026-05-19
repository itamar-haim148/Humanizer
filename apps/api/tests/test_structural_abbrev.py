"""Regression tests for abbreviation-aware sentence splitting and JSON dict
hygiene (no duplicate keys, no self-substitutions, no clitic-eating phrases).
"""

from __future__ import annotations

import json
from pathlib import Path

from humanizer.engines import structural
from humanizer.engines.structural import _split_sentences


# ---------------------------------------------------------------------------
# Sentence splitter — abbreviations must NOT trigger a split
# ---------------------------------------------------------------------------


def test_does_not_split_after_mr() -> None:
    out = _split_sentences("Mr. Smith arrived early. He was tired.")
    assert len(out) == 2
    assert out[0].startswith("Mr. Smith")


def test_does_not_split_after_dr() -> None:
    out = _split_sentences("Dr. Brown said hello. Then she left.")
    assert len(out) == 2
    assert out[0].startswith("Dr. Brown")


def test_does_not_split_after_eg() -> None:
    out = _split_sentences("Use a fruit, e.g. Apple or Pear. Then continue.")
    assert len(out) == 2


def test_does_not_split_after_us() -> None:
    out = _split_sentences("The U.S. economy grew. Markets cheered.")
    assert len(out) == 2


def test_splits_normal_sentence_boundary() -> None:
    out = _split_sentences("This is one. This is two.")
    assert len(out) == 2


def test_humanizer_preserves_dr_abbreviation_end_to_end() -> None:
    """Run the full structural pipeline and confirm 'Dr.' never starts
    a new sentence with a capital boundary artefact."""
    text = "Dr. Brown joined the team. He brought new ideas to the table."
    out = structural.humanize_structural(text, "en", "aggressive")
    # No corruption: still recognisable as 'Dr. Brown' followed by a sentence.
    assert "Dr. Brown" in out


# ---------------------------------------------------------------------------
# Dictionary hygiene
# ---------------------------------------------------------------------------


_API_ROOT = Path(__file__).resolve().parents[1] / "humanizer" / "engines"


def _load_raw_dict(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _detect_duplicates(raw_text: str, section: str) -> list[str]:
    """JSON silently overwrites duplicate keys. We detect them by walking the
    serialised text. Returns the list of duplicated keys inside *section*.
    """
    import re as _re

    # Locate the section block.
    m = _re.search(rf'"{section}"\s*:\s*\{{', raw_text)
    if not m:
        return []
    # Track brace depth from the opening "{".
    start = m.end() - 1
    depth = 0
    end = start
    for i in range(start, len(raw_text)):
        if raw_text[i] == "{":
            depth += 1
        elif raw_text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    block = raw_text[start:end]
    keys = _re.findall(r'"((?:[^"\\]|\\.)*)"\s*:', block)
    seen: set[str] = set()
    dupes: list[str] = []
    for k in keys:
        if k in seen:
            dupes.append(k)
        seen.add(k)
    return dupes


def test_no_duplicate_keys_in_en_ai_phrases() -> None:
    path = _API_ROOT / "ai_phrases" / "en.json"
    raw = path.read_text(encoding="utf-8")
    for section in ("single_words", "phrases"):
        dupes = _detect_duplicates(raw, section)
        assert not dupes, f"duplicate keys in en.json[{section}]: {dupes}"


def test_no_duplicate_keys_in_he_ai_phrases() -> None:
    path = _API_ROOT / "ai_phrases" / "he.json"
    raw = path.read_text(encoding="utf-8")
    for section in ("single_words", "phrases"):
        dupes = _detect_duplicates(raw, section)
        assert not dupes, f"duplicate keys in he.json[{section}]: {dupes}"


def test_no_self_substitutions_in_he() -> None:
    raw = _load_raw_dict(_API_ROOT / "ai_phrases" / "he.json")
    for word, options in raw.get("single_words", {}).items():
        assert word not in options, f"self-substitution: {word} -> {word}"
    for phrase, replacement in raw.get("phrases", {}).items():
        assert phrase != replacement, f"self-substitution phrase: {phrase!r}"


def test_no_self_substitutions_in_en() -> None:
    raw = _load_raw_dict(_API_ROOT / "ai_phrases" / "en.json")
    for word, options in raw.get("single_words", {}).items():
        assert word not in options
    for phrase, replacement in raw.get("phrases", {}).items():
        assert phrase != replacement


def test_no_dangerous_he_clitic_phrase() -> None:
    """Hebrew phrases must not end on a *standalone* clitic letter —
    i.e. ``" ל"`` or ``" ש"`` at the end of the phrase. Those would
    consume the next word's prefix and produce garbage like
    ``'בנוסף ל' + 'עבודה' → 'וגםעבודה'``.

    Multi-letter trailing tokens like ``"של"`` (the word "of") are safe
    because the trailing letter belongs to a complete word, not a clitic.
    """
    raw = _load_raw_dict(_API_ROOT / "ai_phrases" / "he.json")
    clitic_letters = ("ל", "ב", "מ", "ה", "ו", "כ", "ש")
    for phrase, rep in raw.get("phrases", {}).items():
        if len(phrase) >= 2 and phrase[-2] == " " and phrase[-1] in clitic_letters:
            # Replacement must preserve the clitic at the end so the next
            # word's prefix is still attached.
            assert rep.endswith(phrase[-1]), (
                f"dangerous phrase {phrase!r} -> {rep!r} would eat the next word"
            )
