"""Stealth pass — Layer 6.

Two sub-passes that operate on already-cleaned text:

  6a Perplexity injection: swap high-probability AI tokens for lower-prob
     alternatives ~60% of the time. Seeded RNG → deterministic given the
     same input + seed.

  6b Burstiness fragment injection: after long sentences (>20 words) inside
     a paragraph, occasionally append a short emphasis sentence to vary
     sentence-length distribution (the "burstiness" metric).

Both passes skip:
  - Lines classified as heading / list_item / label_line / code / blank
    (via `protect.classify_lines`)
  - Substrings inside protected ranges (URLs, code, brand names) via
    `protect.lexical_protected_ranges`

Strength mapping:
  - light      → 1 perplexity pass
  - medium     → 1 perplexity pass (default)
  - aggressive → 2 perplexity passes (compounding rewrites)
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


_DATA_DIR = Path(__file__).parent / "_data"
_PERPLEXITY_VOCAB: dict[str, list[str]] = json.loads(
    (_DATA_DIR / "perplexity_vocab.json").read_text(encoding="utf-8")
)
_EMPHASIS_FRAGMENTS: list[str] = json.loads(
    (_DATA_DIR / "emphasis_fragments.json").read_text(encoding="utf-8")
)


@dataclass
class StealthResult:
    text: str
    transformations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 6a Perplexity injection
# ---------------------------------------------------------------------------

_PERPLEXITY_KEYS_SORTED = sorted(_PERPLEXITY_VOCAB.keys(), key=len, reverse=True)
_PERPLEXITY_COMPILED: list[tuple[re.Pattern[str], list[str]]] = [
    (re.compile(rf"\b{re.escape(tok)}\b", re.IGNORECASE), _PERPLEXITY_VOCAB[tok])
    for tok in _PERPLEXITY_KEYS_SORTED
]
_REPLACE_PROBABILITY = 0.6


def _match_case(original: str, replacement: str) -> str:
    if original and original[0].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _perplexity_pass_once(text: str, rng: random.Random) -> tuple[str, int]:
    swap_count = 0

    def _swap(m: re.Match[str], _alts: list[str]) -> str:
        nonlocal swap_count
        if rng.random() > _REPLACE_PROBABILITY:
            return m.group(0)
        choice = _alts[rng.randrange(len(_alts))]
        swap_count += 1
        return _match_case(m.group(0), choice)

    for pat, alts in _PERPLEXITY_COMPILED:
        text = pat.sub(lambda m, a=alts: _swap(m, a), text)
    return text, swap_count


# ---------------------------------------------------------------------------
# 6b Burstiness fragment injection
# ---------------------------------------------------------------------------

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_FRAGMENT_PROBABILITY = 0.35
_LONG_SENTENCE_WORD_THRESHOLD = 20


def _is_injectable_paragraph(paragraph: str) -> bool:
    """Skip headings, lists, code, blockquotes."""
    if not paragraph.strip():
        return False
    lines = protect.classify_lines(paragraph)
    # Any non-prose, non-blank line disqualifies the paragraph.
    for line in lines:
        if line.kind not in ("prose", "blank"):
            return False
    return True


def _burstiness_inject(
    text: str, rng: random.Random, used: set[str]
) -> tuple[str, int]:
    """Walk paragraphs (double-newline separated). For each prose paragraph,
    after the first long sentence, optionally append an unused fragment."""
    parts = re.split(r"(\n\s*\n)", text)
    insertions = 0
    out_parts: list[str] = []
    for chunk in parts:
        # Separators (the matched `\n\s*\n`) pass through unchanged.
        if re.fullmatch(r"\n\s*\n", chunk):
            out_parts.append(chunk)
            continue
        if not _is_injectable_paragraph(chunk):
            out_parts.append(chunk)
            continue
        sentences = _SENTENCE_SPLIT_RE.split(chunk)
        injected = False
        new_sentences: list[str] = []
        for sent in sentences:
            new_sentences.append(sent)
            if injected:
                continue
            wc = len(sent.split())
            if wc < _LONG_SENTENCE_WORD_THRESHOLD:
                continue
            if rng.random() > _FRAGMENT_PROBABILITY:
                continue
            # Pick an unused fragment.
            choices = [f for f in _EMPHASIS_FRAGMENTS if f not in used]
            if not choices:
                continue
            chosen = choices[rng.randrange(len(choices))]
            used.add(chosen)
            new_sentences.append(chosen)
            injected = True
            insertions += 1
        out_parts.append(" ".join(new_sentences))
    return "".join(out_parts), insertions


# ---------------------------------------------------------------------------
# Protected-range aware wrapper
# ---------------------------------------------------------------------------


def _apply_outside_protected(
    text: str, fn, ranges: list[tuple[int, int]]
) -> str:
    if not ranges:
        return fn(text)
    out: list[str] = []
    cursor = 0
    for start, end in ranges:
        if cursor < start:
            out.append(fn(text[cursor:start]))
        out.append(text[start:end])
        cursor = end
    if cursor < len(text):
        out.append(fn(text[cursor:]))
    return "".join(out)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def stealth_pass(
    text: str,
    strength: Strength = "medium",
    seed: int = 42,
) -> StealthResult:
    """Run perplexity injection + burstiness fragment insertion."""
    if not text:
        return StealthResult(text=text)

    n_perplexity_passes = 2 if strength == "aggressive" else 1
    ranges = protect.lexical_protected_ranges(text)

    rng = random.Random(seed)
    total_swaps = 0
    current = text
    for _ in range(n_perplexity_passes):
        def _pass(segment: str) -> str:
            nonlocal total_swaps
            new_segment, n = _perplexity_pass_once(segment, rng)
            total_swaps += n
            return new_segment
        current = _apply_outside_protected(current, _pass, ranges)
        # Re-compute ranges after substitution can shift offsets; protect runs
        # are short and infrequent so we accept the cost.
        ranges = protect.lexical_protected_ranges(current)

    used_fragments: set[str] = set()
    current, n_fragments = _burstiness_inject(current, rng, used_fragments)

    transformations: list[str] = []
    if total_swaps:
        transformations.append(f"stealth:perplexity:{total_swaps}")
    if n_fragments:
        transformations.append(f"stealth:burstiness:{n_fragments}")
    return StealthResult(text=current, transformations=transformations)
