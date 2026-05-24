"""Content classification + protected-region computation.

Engines (lexical, structural) consult these helpers so they leave non-prose
content untouched. The original engine output mangled meta-titles, list
headings, brand names and parenthetical metadata — this module is the fix.

Two public APIs:

    classify_lines(text)            -> list[Line]
    lexical_protected_ranges(text)  -> list[(start, end)]

A "Line" carries its line-relative *body_start*: the offset at which the
transformable body begins (i.e. *after* a label prefix or list marker).
The structural engine uses line classification to skip headings entirely
and to keep list markers (`1.`, `-`, `*`, …) glued to their body.

`lexical_protected_ranges` returns absolute character ranges that
substring-based engines must skip. These cover:

  * URLs and email addresses
  * Inline / fenced code spans
  * Parenthetical metadata that contains digits (e.g. "(48 characters)")
  * Runs of 2+ consecutive Title-Case tokens (likely brand / proper nouns)
  * Heading lines in full
  * The prefix of label/list lines (so the marker / label cannot be edited)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

__all__ = [
    "Line",
    "LineKind",
    "classify_lines",
    "is_protected",
    "lexical_protected_ranges",
]

LineKind = Literal["prose", "heading", "list_item", "label_line", "code", "blank"]


@dataclass(frozen=True)
class Line:
    start: int
    end: int  # exclusive of trailing newline
    text: str
    kind: LineKind
    body_start: int  # offset relative to `text` where transformable body begins


# ---------------------------------------------------------------------------
# Regex catalogue
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"\b(?:https?://|www\.)[^\s<>\"'\)]+",
    flags=re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FENCED_CODE_RE = re.compile(r"```[\s\S]*?```", flags=re.MULTILINE)
_PARENTHETICAL_META_RE = re.compile(r"\([^()\n]*\d[^()\n]*\)")

# Markdown link / image syntax (StealthHumanizer patterns).
# Image: ![alt](url)   Link: [text](url)   Reference: [text][ref] or [text][]
#
# The URL portion allows ONE level of balanced parens to handle URLs like
# https://en.wikipedia.org/wiki/Foo_(bar) — the most common real-world case
# of unescaped parens. Full balance-matching needs PCRE recursion which
# `re` doesn't support; one level catches >99% of pasted Markdown.
_MD_URL_BODY = r"[^()\n]*(?:\([^()\n]*\)[^()\n]*)*"
_MD_IMAGE_RE = re.compile(rf"!\[[^\]\n]*\]\({_MD_URL_BODY}\)")
_MD_LINK_INLINE_RE = re.compile(rf"(?<!\!)\[[^\]\n]+\]\({_MD_URL_BODY}\)")
_MD_LINK_REF_RE = re.compile(r"(?<!\!)\[[^\]\n]+\]\[[^\]\n]*\]")
# Reference definition line: "[ref]: https://example.com optional title"
# Excludes footnote definitions ("[^1]: ..."): those are content, not URL refs,
# and need to remain transformable (they often contain prose).
_MD_LINK_REF_DEF_RE = re.compile(
    r"^\s*\[(?!\^)[^\]\n]+\]:\s+\S.*$", flags=re.MULTILINE
)

# Social mentions and hashtags. Common in marketing copy that gets pasted in.
# Mentions: @username  Hashtags: #topic  (ASCII + Hebrew letters allowed)
_MENTION_RE = re.compile(r"(?<![A-Za-z0-9_])@[A-Za-z0-9_\u05D0-\u05EA][A-Za-z0-9_\.\-\u05D0-\u05EA]{0,49}")
_HASHTAG_RE = re.compile(r"(?<![A-Za-z0-9_])#[A-Za-z0-9_\u05D0-\u05EA][A-Za-z0-9_\u05D0-\u05EA]{0,49}")

# 2+ consecutive Title-Case tokens — likely a proper noun / brand / product name.
# Each token requires 2+ characters to avoid catching "I" or single-letter
# initials. We accept hyphens, ampersands, digits within a token.
_PROPER_NOUN_RUN_RE = re.compile(
    r"(?:[A-Z][A-Za-z0-9&\-]+(?:\s+|$)){2,}"
)

# Line-start markers.
_HEADING_HASH_RE = re.compile(r"^\s*#{1,6}\s+")
_LIST_MARKER_RE = re.compile(r"^\s*(?:\d+[.)]|[-*\u2022\u2013])\s+")
_BLOCKQUOTE_RE = re.compile(r"^\s*(?:>\s*)+")

# Label pattern, e.g.
#   "Title:"
#   "Meta Title:"
#   "Meta Description (154 characters):"
#   "כותרת ראשית:"
# Restricted to <=8 leading capitalised / Hebrew tokens so we don't match
# whole sentences that happen to contain a colon.
_LABEL_TOKEN = r"[A-Z\u05D0-\u05EA][\w&/\-\u05D0-\u05EA]*"
_LABEL_NEXT = r"[A-Z\d\u05D0-\u05EA][\w&/\-\u05D0-\u05EA]*"
_LABEL_LINE_RE = re.compile(
    r"^\s*"
    rf"(?P<label>{_LABEL_TOKEN}(?:\s+{_LABEL_NEXT}){{0,7}})"
    r"(?P<paren>\s*\([^)\n]+\))?"
    r"\s*:\s+"
    r"(?=\S)"  # require at least one body character on the same line
)


_HEADING_MAX_WORDS = 8
_TERMINATORS = (".", "!", "?", ":", ";")


# ---------------------------------------------------------------------------
# Line classification
# ---------------------------------------------------------------------------


def _classify_line(line: str) -> tuple[LineKind, int]:
    """Return ``(kind, body_start)`` for a single line (no trailing newline)."""
    stripped = line.strip()
    if not stripped:
        return "blank", 0

    # Hash-style heading.
    m = _HEADING_HASH_RE.match(line)
    if m:
        return "heading", 0

    # Blockquote — protect the "> " marker(s), allow body to be transformed
    # as prose. A short body without terminal punctuation is promoted to
    # heading (consistent with list-marker behaviour).
    m = _BLOCKQUOTE_RE.match(line)
    if m:
        body = line[m.end():].strip()
        no_terminator = not body.endswith(_TERMINATORS)
        is_short = len(body.split()) <= _HEADING_MAX_WORDS
        if no_terminator and is_short:
            return "heading", 0
        return "list_item", m.end()

    # List item.
    m = _LIST_MARKER_RE.match(line)
    if m:
        body = line[m.end():].strip()
        no_terminator = not body.endswith(_TERMINATORS)
        is_short = len(body.split()) <= _HEADING_MAX_WORDS
        if no_terminator and is_short:
            # "1. Section Heading" — treat the whole line as a heading.
            return "heading", 0
        return "list_item", m.end()

    # Label line: "Meta Title (X characters): body…"
    m = _LABEL_LINE_RE.match(line)
    if m:
        return "label_line", m.end()

    # Short line without terminal punctuation → heading.
    if (
        len(stripped.split()) <= _HEADING_MAX_WORDS
        and not stripped.endswith(_TERMINATORS)
    ):
        return "heading", 0

    return "prose", 0


def classify_lines(text: str) -> list[Line]:
    """Split *text* on ``\\n`` and classify each line."""
    lines: list[Line] = []
    cursor = 0
    for raw in text.split("\n"):
        end = cursor + len(raw)
        kind, body_start = _classify_line(raw)
        lines.append(
            Line(
                start=cursor,
                end=end,
                text=raw,
                kind=kind,
                body_start=body_start,
            )
        )
        cursor = end + 1  # +1 for the newline
    return lines


# ---------------------------------------------------------------------------
# Lexical protected ranges
# ---------------------------------------------------------------------------


def _sentence_initial(text: str, pos: int) -> bool:
    """True if `pos` is the first non-space character of a sentence/line."""
    if pos == 0:
        return True
    # Walk left over whitespace.
    j = pos - 1
    while j >= 0 and text[j] in " \t":
        j -= 1
    if j < 0:
        return True
    return text[j] in ".!?:\n"


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: list[list[int]] = [list(ranges[0])]
    for s, e in ranges[1:]:
        if s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def lexical_protected_ranges(
    text: str, *, protect_headings: bool = True
) -> list[tuple[int, int]]:
    """Character ranges that lexical substitution engines must skip.

    `protect_headings`: when False, full heading lines are NOT added to the
    protected set. Useful for AI-tell scrubbing where heading bodies (like
    "Why This Matters In Today's Digital Landscape") need to be edited.
    Brand-name protection inside the heading still applies via the
    proper-noun run detector.
    """
    ranges: list[tuple[int, int]] = []

    # Code spans first (so URLs inside backticks aren't double-counted, etc.).
    for rx in (_FENCED_CODE_RE, _INLINE_CODE_RE):
        for m in rx.finditer(text):
            ranges.append((m.start(), m.end()))

    # Markdown images/links before URL detection so the [text](url) construct
    # is protected as a whole, not just the url portion.
    for rx in (_MD_IMAGE_RE, _MD_LINK_INLINE_RE, _MD_LINK_REF_RE, _MD_LINK_REF_DEF_RE):
        for m in rx.finditer(text):
            ranges.append((m.start(), m.end()))

    for rx in (_URL_RE, _EMAIL_RE, _PARENTHETICAL_META_RE, _MENTION_RE, _HASHTAG_RE):
        for m in rx.finditer(text):
            ranges.append((m.start(), m.end()))

    # Proper-noun runs.
    #
    # Mid-sentence: any 2+ Title-Case tokens are treated as a brand / proper
    # noun and fully protected.
    #
    # Sentence-initial: capitalised tokens are ambiguous (sentence start
    # could just be sentence capitalisation). We require >= 3 tokens to
    # accept a sentence-initial run as a proper noun, and even then we drop
    # the first token from the protected range (it's the natural sentence
    # opener). 2-token sentence-initial runs like "Get Started" are NOT
    # protected at all — they may legitimately be transformed.
    for m in _PROPER_NOUN_RUN_RE.finditer(text):
        run_start = m.start()
        run_end = m.end()
        if _sentence_initial(text, run_start):
            tokens = list(re.finditer(r"[A-Z][A-Za-z0-9&\-]+", m.group(0)))
            if len(tokens) >= 3:
                second_global = run_start + tokens[1].start()
                if second_global < run_end:
                    ranges.append((second_global, run_end))
            # 2-token sentence-initial run: no protection.
        else:
            ranges.append((run_start, run_end))

    # Line-level protections.
    for line in classify_lines(text):
        if line.kind == "heading":
            if protect_headings:
                ranges.append((line.start, line.end))
        elif line.kind in ("list_item", "label_line"):
            ranges.append((line.start, line.start + line.body_start))

    return _merge_ranges(ranges)


def is_protected(pos: int, ranges: list[tuple[int, int]]) -> bool:
    """Whether the character index *pos* is inside any protected range.

    Uses a linear scan with early exit; ranges are pre-sorted and merged so
    the loop runs in O(matches) per call which is fine in practice — the
    largest inputs we see have a few dozen ranges at most.
    """
    for s, e in ranges:
        if pos < s:
            return False
        if pos < e:
            return True
    return False


def overlaps_protected(
    start: int, end: int, ranges: list[tuple[int, int]]
) -> bool:
    """Whether the half-open span ``[start, end)`` touches any protected range."""
    for s, e in ranges:
        if e <= start:
            continue
        if s >= end:
            return False
        return True
    return False
