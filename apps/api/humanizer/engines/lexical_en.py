"""English lexical humanizer.

Layered substitution:

  1. Multi-word AI phrases (longest first, case-insensitive).
  2. Single-word AI-typical vocabulary (formal → casual register shift).
  3. General-purpose synonyms (low rate, conservative dictionary).

Substitutions skip any character span returned by
``protect.lexical_protected_ranges``: URLs, emails, code spans,
parenthetical metadata, proper-noun runs, heading lines and label/list
prefixes. Combined with a tight, register-shift-only synonym dictionary
this prevents the engine from mangling meta-titles, brand names or
list-item headings.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from humanizer.engines import protect

Strength = Literal["light", "medium", "aggressive"]

_DATA_DIR = Path(__file__).parent
_AI_PHRASES_PATH = _DATA_DIR / "ai_phrases" / "en.json"
_SYNONYMS_PATH = _DATA_DIR / "synonyms" / "en.json"

_STRENGTH_RATIO: dict[Strength, float] = {
    "light": 0.20,
    "medium": 0.50,
    "aggressive": 0.85,
}

# How much of the strength ratio applies to the general synonym pass.
# Synonyms are riskier than AI-phrase swaps, so we apply them sparingly.
# 0.30 means at aggressive (ratio=0.85) each candidate has a ~25% chance of
# being swapped — visible variety without compounding into nonsense.
_SYN_RATIO_SCALE = 0.30

_RNG_SEED = 1729


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


def _match_case(template: str, replacement: str) -> str:
    if template.isupper():
        return replacement.upper()
    if template[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def humanize_lexical(text: str, strength: Strength) -> LexicalResult:
    """Apply lexical swaps. Returns text + list of human-readable transformations."""
    if not text:
        return LexicalResult(text="")

    ratio = _STRENGTH_RATIO[strength]
    rng = random.Random(f"{_RNG_SEED}:{strength}:{len(text)}")
    transformations: list[str] = []

    protected = protect.lexical_protected_ranges(text)

    def _protected(start: int, end: int) -> bool:
        return protect.overlaps_protected(start, end, protected)

    # 1) Multi-word phrases first (longest first, case-insensitive).
    result_parts: list[tuple[str, list[tuple[int, int]]]] = [(text, protected)]
    result = text

    for phrase, replacement in sorted(_AI_PHRASES.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        # We must recompute protected ranges if the text mutates, but for
        # phrases the change in length would shift offsets. The simplest robust
        # approach: scan matches first, decide which to apply, then build
        # the new string in one pass.
        spans: list[tuple[int, int, str]] = []
        for m in pattern.finditer(result):
            if _protected(m.start(), m.end()):
                continue
            if rng.random() > ratio:
                continue
            cased = _match_case(m.group(0), replacement)
            spans.append((m.start(), m.end(), cased))
            transformations.append(f"phrase: '{m.group(0)}' → '{cased}'")

        if spans:
            out: list[str] = []
            cursor = 0
            for s, e, rep in spans:
                out.append(result[cursor:s])
                out.append(rep)
                cursor = e
            out.append(result[cursor:])
            result = "".join(out)
            # Protected ranges become stale after a length-changing edit; we
            # recompute once. Phrase replacements are rare so this is cheap.
            protected = protect.lexical_protected_ranges(result)

    # 2) Single-word AI vocabulary.
    def _word_swap(match: re.Match[str]) -> str:
        if _protected(match.start(), match.end()):
            return match.group(0)
        original = match.group(0)
        options = _AI_WORDS.get(original.lower())
        if options is None:
            return original
        if rng.random() > ratio:
            return original
        choice = rng.choice(options)
        cased = _match_case(original, choice)
        transformations.append(f"word: '{original}' → '{cased}'")
        return cased

    result = re.sub(r"\b[A-Za-z'\-]+\b", _word_swap, result)
    protected = protect.lexical_protected_ranges(result)

    # 3) General synonym variety (lower ratio than the AI vocab pass).
    syn_ratio = ratio * _SYN_RATIO_SCALE

    def _syn_swap(match: re.Match[str]) -> str:
        if _protected(match.start(), match.end()):
            return match.group(0)
        original = match.group(0)
        options = _SYNONYMS.get(original.lower())
        if options is None:
            return original
        if rng.random() > syn_ratio:
            return original
        choice = rng.choice(options)
        cased = _match_case(original, choice)
        transformations.append(f"syn: '{original}' → '{cased}'")
        return cased

    result = re.sub(r"\b[A-Za-z'\-]+\b", _syn_swap, result)

    return LexicalResult(text=result, transformations=transformations)
