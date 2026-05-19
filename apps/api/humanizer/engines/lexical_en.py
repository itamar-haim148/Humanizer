"""English lexical humanizer.

Ports the "Dynamic Contextual Replacement Engine" idea from
OrbitWebTools/Humanize-AI and the synonym-swap layer (Layer 2) from
rudra496/StealthHumanizer. Runs entirely offline.

The engine:
  1. Loads AI-typical phrase + single-word dictionaries
  2. Replaces matches based on `strength` probability
  3. Preserves case and (for single words) trailing -s/-es plural forms
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
_AI_PHRASES_PATH = _DATA_DIR / "ai_phrases" / "en.json"
_SYNONYMS_PATH = _DATA_DIR / "synonyms" / "en.json"

_STRENGTH_RATIO: dict[Strength, float] = {
    "light": 0.20,
    "medium": 0.50,
    "aggressive": 0.85,
}

# Seed makes replacements deterministic per (text, strength).
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

    # 1) Multi-word phrases first (greedy, case-insensitive)
    result = text
    for phrase, replacement in sorted(_AI_PHRASES.items(), key=lambda kv: -len(kv[0])):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        def _sub(match: re.Match[str], rep: str = replacement) -> str:
            if rng.random() > ratio:
                return match.group(0)
            cased = _match_case(match.group(0), rep)
            transformations.append(f"phrase: '{match.group(0)}' → '{cased}'")
            return cased

        result = pattern.sub(_sub, result)

    # 2) Single-word AI vocabulary
    def _word_swap(match: re.Match[str]) -> str:
        original = match.group(0)
        lower = original.lower()
        options = _AI_WORDS.get(lower)
        if options is None:
            return original
        if rng.random() > ratio:
            return original
        choice = rng.choice(options)
        cased = _match_case(original, choice)
        transformations.append(f"word: '{original}' → '{cased}'")
        return cased

    result = re.sub(r"\b[A-Za-z'-]+\b", _word_swap, result)

    # 3) General synonym variety (lower ratio than AI vocab)
    syn_ratio = ratio * 0.35  # gentler so we don't over-rewrite

    def _syn_swap(match: re.Match[str]) -> str:
        original = match.group(0)
        lower = original.lower()
        options = _SYNONYMS.get(lower)
        if options is None:
            return original
        if rng.random() > syn_ratio:
            return original
        choice = rng.choice(options)
        cased = _match_case(original, choice)
        transformations.append(f"syn: '{original}' → '{cased}'")
        return cased

    result = re.sub(r"\b[A-Za-z'-]+\b", _syn_swap, result)

    return LexicalResult(text=result, transformations=transformations)
