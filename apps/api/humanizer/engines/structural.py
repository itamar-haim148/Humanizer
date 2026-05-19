"""Structural humanizer — sentence-length variation + burstiness injection.

Statistical detectors flag AI text by *low burstiness* (uniform sentence
lengths). This engine:

  1. Splits long sentences at conjunctions to inject short ones.
  2. Merges very short adjacent sentences with appropriate connectors.
  3. At medium+ strength, optionally swaps one sentence opener per paragraph
     to a punchy starter ("But", "Still", "Then" / "אבל", "ובכל זאת", "אז").

Acceptance target: stdev/mean of sentence lengths (= burstiness) of the
output should be measurably higher than the input on uniform AI corpora.
"""

from __future__ import annotations

import random
import re
from typing import Literal

Language = Literal["en", "he"]
Strength = Literal["light", "medium", "aggressive"]

_RNG_SEED = 1729

# Splitter that keeps the terminal punctuation glued to each sentence.
_SENTENCE_SPLIT_EN = re.compile(r"(?<=[.!?])\s+(?=[A-Z\u05D0-\u05EA])")
_SENTENCE_SPLIT_HE = re.compile(r"(?<=[.!?])\s+(?=[\u05D0-\u05EAA-Z])")

# Conjunctions where we may split long sentences. Kept short so we don't
# explode every sentence apart.
_SPLIT_CONJUNCTIONS_EN = (", and ", ", but ", "; however, ", ", which ", ", because ")
_SPLIT_CONJUNCTIONS_HE = (", וכן ", ", אבל ", ", אך ", ", כי ", "; אולם ")

_PUNCHY_OPENERS_EN = ("But ", "Still, ", "Then ", "So, ", "And ")
_PUNCHY_OPENERS_HE = ("אבל ", "ובכל זאת, ", "אז ", "וגם ", "ולכן ")

_LONG_EN_WORDS = 28
_LONG_HE_WORDS = 22
_SHORT_WORDS = 6


def _split_sentences(text: str, lang: Language) -> list[str]:
    splitter = _SENTENCE_SPLIT_EN if lang == "en" else _SENTENCE_SPLIT_HE
    chunks = [s.strip() for s in splitter.split(text) if s.strip()]
    return chunks


def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", s) if w])


def humanize_structural(text: str, language: Language, strength: Strength) -> str:
    """Return text rewritten with more sentence-length variety."""
    if not text or strength == "light":
        return text

    rng = random.Random(f"{_RNG_SEED}:{language}:{strength}:{len(text)}")

    # Operate per paragraph so we don't merge sentences across blank lines.
    paragraphs = re.split(r"(\n{2,}|\n)", text)
    rewritten: list[str] = []

    for para in paragraphs:
        if not para or para.isspace() or para.startswith("\n"):
            rewritten.append(para)
            continue
        sentences = _split_sentences(para, language)
        if not sentences:
            rewritten.append(para)
            continue

        long_threshold = _LONG_EN_WORDS if language == "en" else _LONG_HE_WORDS
        conjunctions = (
            _SPLIT_CONJUNCTIONS_EN if language == "en" else _SPLIT_CONJUNCTIONS_HE
        )

        # 1) Split long sentences at the first matching conjunction.
        split_results: list[str] = []
        for s in sentences:
            if _word_count(s) > long_threshold:
                for conj in conjunctions:
                    idx = s.find(conj)
                    if idx > 10:
                        first = s[:idx].rstrip(" ,;") + "."
                        rest_raw = s[idx + len(conj):]
                        rest = rest_raw[:1].upper() + rest_raw[1:] if language == "en" else rest_raw
                        split_results.append(first)
                        split_results.append(rest)
                        break
                else:
                    split_results.append(s)
            else:
                split_results.append(s)

        # 2) Merge short adjacent sentences.
        merged: list[str] = []
        i = 0
        while i < len(split_results):
            cur = split_results[i]
            if (
                i + 1 < len(split_results)
                and _word_count(cur) < _SHORT_WORDS
                and _word_count(split_results[i + 1]) < _SHORT_WORDS
            ):
                nxt = split_results[i + 1]
                joiner = " — " if language == "en" else " — "
                stripped = cur.rstrip(".!?")
                merged.append(f"{stripped}{joiner}{nxt}")
                i += 2
            else:
                merged.append(cur)
                i += 1

        # 3) Punchy opener swap (at medium+, one per paragraph)
        if merged and strength in ("medium", "aggressive"):
            openers = _PUNCHY_OPENERS_EN if language == "en" else _PUNCHY_OPENERS_HE
            target_idx = 0 if len(merged) == 1 else 1
            target = merged[target_idx]
            opener = rng.choice(openers)
            first_word, _, rest = target.partition(" ")
            if rest and not target.startswith(openers):
                merged[target_idx] = f"{opener}{first_word.lower()} {rest}"

        rewritten.append(" ".join(merged))

    return "".join(rewritten)


def burstiness(text: str, language: Language) -> float:
    """stdev / mean of sentence word counts. Higher = burstier."""
    sentences = _split_sentences(text, language)
    counts = [_word_count(s) for s in sentences if s.strip()]
    if not counts:
        return 0.0
    n = len(counts)
    mean = sum(counts) / n
    if mean == 0:
        return 0.0
    var = sum((c - mean) ** 2 for c in counts) / n
    stdev = var ** 0.5
    return stdev / mean
