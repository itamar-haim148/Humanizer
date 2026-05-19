"""Hebrew lexical humanizer.

Hebrew-specific concerns vs the English engine:

  * **Niqqud (vowel marks)**: Match by stripping niqqud (combining marks in
    range U+0591–U+05C7) before comparing; restore on output where the swap
    is unambiguous (we replace whole tokens, so niqqud is dropped from the
    replacement — typical for modern Hebrew web text which is mostly bare).
  * **Prefixes**: Hebrew clitics attach to words: ה (definite article),
    ו (conjunction), ב/ל/מ/כ/ש (prepositions/relativizers). Match those
    optionally and re-prepend them on the replacement.
  * **Word boundaries**: The default `\\b` regex does not work cleanly for
    Hebrew (`\\b` in Python's `re` is locale-blind for Unicode letters when
    using the default flags); we build an explicit Hebrew-letter character
    class and use lookarounds.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Strength = Literal["light", "medium", "aggressive"]

_DATA_DIR = Path(__file__).parent
_AI_PHRASES_PATH = _DATA_DIR / "ai_phrases" / "he.json"
_SYNONYMS_PATH = _DATA_DIR / "synonyms" / "he.json"

_STRENGTH_RATIO: dict[Strength, float] = {
    "light": 0.20,
    "medium": 0.50,
    "aggressive": 0.85,
}

_RNG_SEED = 1729

# Niqqud / cantillation range.
_NIQQUD_RE = re.compile(r"[\u0591-\u05C7]")

# Inseparable prefixes (single letters). ש and מ are also common as standalone
# words so handled below at lookaround level.
_PREFIXES = ("ה", "ו", "ב", "ל", "מ", "כ", "ש", "וה", "וב", "ול", "ומ", "וכ", "וש")

# Hebrew letter class (no niqqud — niqqud is stripped before matching).
_HE_LETTER = r"[\u05D0-\u05EA]"

# Sort prefixes by length (longest first) for greedy match.
_PREFIXES_SORTED = sorted(_PREFIXES, key=len, reverse=True)
_PREFIX_GROUP = "|".join(re.escape(p) for p in _PREFIXES_SORTED)


@dataclass
class LexicalResult:
    text: str
    transformations: list[str] = field(default_factory=list)


def _load() -> tuple[dict[str, list[str]], dict[str, str], dict[str, list[str]]]:
    with _AI_PHRASES_PATH.open(encoding="utf-8") as f:
        ai = json.load(f)
    with _SYNONYMS_PATH.open(encoding="utf-8") as f:
        syn = json.load(f)
    return ai.get("single_words", {}), ai.get("phrases", {}), syn


_AI_WORDS, _AI_PHRASES, _SYNONYMS = _load()


def _strip_niqqud(s: str) -> str:
    return _NIQQUD_RE.sub("", s)


def _is_hebrew_letter(ch: str) -> bool:
    return "\u05D0" <= ch <= "\u05EA"


def humanize_lexical_he(text: str, strength: Strength) -> LexicalResult:
    """Apply Hebrew-aware lexical swaps."""
    if not text:
        return LexicalResult(text="")

    ratio = _STRENGTH_RATIO[strength]
    rng = random.Random(f"{_RNG_SEED}:he:{strength}:{len(text)}")
    transformations: list[str] = []

    # 1) Phrases (greedy, longest first; case-insensitive though Hebrew has no case)
    result = text
    for phrase, replacement in sorted(_AI_PHRASES.items(), key=lambda kv: -len(kv[0])):
        # Build a niqqud-tolerant pattern: insert optional niqqud between letters.
        pattern_chars = []
        for ch in phrase:
            pattern_chars.append(re.escape(ch))
            if _is_hebrew_letter(ch):
                pattern_chars.append(r"[\u0591-\u05C7]*")
        pattern = re.compile("".join(pattern_chars))

        def _sub(match: re.Match[str], rep: str = replacement) -> str:
            if rng.random() > ratio:
                return match.group(0)
            transformations.append(f"phrase: '{match.group(0)}' → '{rep}'")
            return rep

        result = pattern.sub(_sub, result)

    # 2) Single words — match optional prefix + Hebrew word.
    word_re = re.compile(
        rf"(?:(?P<prefix>{_PREFIX_GROUP})\u05BE?)?(?P<root>{_HE_LETTER}+)"
    )

    def _word_swap(match: re.Match[str], table: dict[str, list[str]]) -> str:
        prefix = match.group("prefix") or ""
        root_raw = match.group("root")
        root = _strip_niqqud(root_raw)
        # First try with prefix included as part of the lookup key (for cases like
        # "בעולם" that may appear directly in the table).
        full = prefix + root
        if full in table:
            if rng.random() > ratio:
                return match.group(0)
            choice = rng.choice(table[full])
            transformations.append(f"word: '{match.group(0)}' → '{choice}'")
            return choice
        if root in table:
            if rng.random() > ratio:
                return match.group(0)
            choice = rng.choice(table[root])
            transformations.append(f"word: '{match.group(0)}' → '{prefix}{choice}'")
            return f"{prefix}{choice}"
        return match.group(0)

    result = word_re.sub(lambda m: _word_swap(m, _AI_WORDS), result)

    # 3) General synonyms — lower ratio so we don't over-rewrite.
    syn_ratio = ratio * 0.35
    rng2 = random.Random(f"{_RNG_SEED}:he-syn:{strength}:{len(text)}")

    def _syn_swap(match: re.Match[str]) -> str:
        prefix = match.group("prefix") or ""
        root_raw = match.group("root")
        root = _strip_niqqud(root_raw)
        full = prefix + root
        if full in _SYNONYMS:
            if rng2.random() > syn_ratio:
                return match.group(0)
            choice = rng2.choice(_SYNONYMS[full])
            transformations.append(f"syn: '{match.group(0)}' → '{choice}'")
            return choice
        if root in _SYNONYMS:
            if rng2.random() > syn_ratio:
                return match.group(0)
            choice = rng2.choice(_SYNONYMS[root])
            transformations.append(f"syn: '{match.group(0)}' → '{prefix}{choice}'")
            return f"{prefix}{choice}"
        return match.group(0)

    result = word_re.sub(_syn_swap, result)

    return LexicalResult(text=result, transformations=transformations)
