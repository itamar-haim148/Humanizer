"""Structural humanizer — sentence-length variation and burstiness injection.

Operates per *line*. Headings, code, list-only headings and blank lines are
emitted verbatim. Prose, label and list-item lines are transformed
in-place: their leading prefix (e.g. ``"1. "`` or ``"Meta Title: "``) is
preserved while the body sentences are split, merged or opener-swapped.

  1. Split overly-long sentences at a conjunction.
  2. Merge short adjacent sentences with an em-dash for cadence variety.
  3. (aggressive only, paragraph with ≥3 sentences) swap the second
     sentence's opener for a punchy alternative.

Sentence splitting is digit-aware so list numbering ("1.") never fragments
the text, and abbreviations like "U.S." remain intact.
"""

from __future__ import annotations

import random
import re
from typing import Literal

from humanizer.engines import protect

Language = Literal["en", "he"]
Strength = Literal["light", "medium", "aggressive"]

_RNG_SEED = 1729

_SENTENCE_SPLIT = re.compile(
    r"(?<![A-Z\d])(?<=[.!?])\s+(?=[A-Z\u05D0-\u05EA])"
)

_SPLIT_CONJUNCTIONS_EN = (
    ", and ",
    ", but ",
    "; however, ",
    ", which ",
    ", because ",
)
_SPLIT_CONJUNCTIONS_HE = (
    ", וכן ",
    ", אבל ",
    ", אך ",
    ", כי ",
    "; אולם ",
)

_PUNCHY_OPENERS_EN = ("But ", "Still, ", "Then ", "And ")
_PUNCHY_OPENERS_HE = ("אבל ", "ובכל זאת, ", "אז ", "וגם ")

_LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*\u2022\u2013])\s+")
_LABEL_PREFIX_RE = re.compile(
    r"^\s*[A-Z][\w&/\-]*(?:\s+[A-Z\d][\w&/\-]*){0,7}(?:\s*\([^)\n]+\))?\s*:\s*"
)

_LONG_EN_WORDS = 28
_LONG_HE_WORDS = 22
_SHORT_WORDS = 6
_MIN_SENTENCES_FOR_OPENER = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _word_count(s: str) -> int:
    return len([w for w in re.split(r"\s+", s) if w])


def _starts_with_list_marker(s: str) -> bool:
    return bool(_LIST_MARKER_RE.match(s))


def _starts_with_label_prefix(s: str) -> bool:
    return bool(_LABEL_PREFIX_RE.match(s))


def _has_punchy_opener(s: str, openers: tuple[str, ...]) -> bool:
    return s.startswith(openers)


def _is_safe_opener_target(sentence: str, openers: tuple[str, ...]) -> bool:
    if _starts_with_list_marker(sentence):
        return False
    if _starts_with_label_prefix(sentence):
        return False
    if _has_punchy_opener(sentence, openers):
        return False
    parts = sentence.split(" ", 2)
    if len(parts) >= 2 and parts[0][:1].isupper() and parts[1][:1].isupper():
        # Proper-noun run at the start — keep it intact.
        return False
    return True


def _split_sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_SPLIT.split(text) if s.strip()]


# ---------------------------------------------------------------------------
# Per-line transformation
# ---------------------------------------------------------------------------


def _split_prefix(line_text: str, line_kind: protect.LineKind, body_start: int) -> tuple[str, str]:
    """Split a single line into (prefix, body) for in-place transformation."""
    if line_kind in ("list_item", "label_line") and body_start > 0:
        return line_text[:body_start], line_text[body_start:]
    return "", line_text


def _transform_body(
    body: str,
    language: Language,
    strength: Strength,
    rng: random.Random,
) -> str:
    if not body.strip():
        return body

    sentences = _split_sentences(body)
    if not sentences:
        return body

    long_threshold = _LONG_EN_WORDS if language == "en" else _LONG_HE_WORDS
    conjunctions = (
        _SPLIT_CONJUNCTIONS_EN if language == "en" else _SPLIT_CONJUNCTIONS_HE
    )
    openers = _PUNCHY_OPENERS_EN if language == "en" else _PUNCHY_OPENERS_HE

    # 1) Split long sentences.
    split_results: list[str] = []
    for s in sentences:
        if _word_count(s) > long_threshold:
            for conj in conjunctions:
                idx = s.find(conj)
                if idx > 10:
                    first = s[:idx].rstrip(" ,;") + "."
                    rest_raw = s[idx + len(conj):]
                    rest = (
                        rest_raw[:1].upper() + rest_raw[1:]
                        if language == "en"
                        else rest_raw
                    )
                    split_results.append(first)
                    split_results.append(rest)
                    break
            else:
                split_results.append(s)
        else:
            split_results.append(s)

    # 2) Merge short adjacent sentences (only when both look like prose).
    merged: list[str] = []
    i = 0
    while i < len(split_results):
        cur = split_results[i]
        nxt = split_results[i + 1] if i + 1 < len(split_results) else None
        can_merge = (
            nxt is not None
            and _word_count(cur) < _SHORT_WORDS
            and _word_count(nxt) < _SHORT_WORDS
            and not _starts_with_list_marker(cur)
            and not _starts_with_list_marker(nxt)
            and not _starts_with_label_prefix(cur)
            and not _starts_with_label_prefix(nxt)
            and not cur.strip().rstrip(".!?").isdigit()
        )
        if can_merge:
            stripped = cur.rstrip(".!?")
            merged.append(f"{stripped} \u2014 {nxt}")
            i += 2
        else:
            merged.append(cur)
            i += 1

    # 3) Opener swap — only at aggressive, only when paragraph has body.
    if strength == "aggressive" and len(merged) >= _MIN_SENTENCES_FOR_OPENER:
        for target_idx in (1, 2):
            if target_idx >= len(merged):
                break
            target = merged[target_idx]
            if not _is_safe_opener_target(target, openers):
                continue
            opener = rng.choice(openers)
            first_word, _, rest = target.partition(" ")
            if not rest:
                continue
            new_first = first_word if first_word.isupper() else first_word.lower()
            merged[target_idx] = f"{opener}{new_first} {rest}"
            break

    return " ".join(merged)


# ---------------------------------------------------------------------------
# Top-level walk
# ---------------------------------------------------------------------------


def humanize_structural(
    text: str, language: Language, strength: Strength
) -> str:
    """Return *text* with structural variety injected on prose lines."""
    if not text or strength == "light":
        return text

    rng = random.Random(f"{_RNG_SEED}:{language}:{strength}:{len(text)}")

    lines = protect.classify_lines(text)
    out_lines: list[str] = []

    for line in lines:
        if line.kind in ("blank", "heading", "code"):
            out_lines.append(line.text)
            continue
        prefix, body = _split_prefix(line.text, line.kind, line.body_start)
        transformed = _transform_body(body, language, strength, rng)
        out_lines.append(prefix + transformed)

    rebuilt = "\n".join(out_lines)

    # Preserve a trailing newline if the original had one (split("\n") on a
    # string ending in "\n" yields a final "" item which we re-emit cleanly).
    if text.endswith("\n") and not rebuilt.endswith("\n"):
        rebuilt += "\n"
    return rebuilt


# ---------------------------------------------------------------------------
# Burstiness — exposed for detector + tests
# ---------------------------------------------------------------------------


def burstiness(text: str, language: Language) -> float:  # noqa: ARG001
    """stdev / mean of sentence word counts. Higher = burstier."""
    sentences = _split_sentences(text)
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
