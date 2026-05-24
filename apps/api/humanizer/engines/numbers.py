"""Number humanization — Layer 3.

Adds comma separators to bare integers >= 1000 (e.g. "12500" → "12,500").
Skips:
  - 4-digit years 1900-2099 (so "2026" stays "2026", not "2,026")
  - Numbers already containing commas, periods, or hyphens
  - Numbers inside protected ranges (URLs, code, brand names)

LLMs write bare integers; humans use comma separators. This is a small but
reliable AI-tell fix.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from humanizer.engines import protect

_NUMBER_RE = re.compile(r"(?<![\d,.\-])(\d{4,})(?![\d,.])")


@dataclass
class NumberResult:
    text: str
    transformations: list[str] = field(default_factory=list)


def _humanize_one(match: re.Match[str]) -> str:
    digits = match.group(1)
    num = int(digits)
    # Year heuristic: exactly 4 digits in [1900, 2099] stay as-is.
    if len(digits) == 4 and 1900 <= num <= 2099:
        return digits
    return f"{num:,}"


def _apply_outside_protected(
    text: str, ranges: list[tuple[int, int]]
) -> tuple[str, int]:
    """Run number humanization on segments NOT inside `ranges`. Returns
    (new_text, replacement_count)."""
    if not ranges:
        new, n = _NUMBER_RE.subn(_humanize_one, text)
        return new, _count_changed(text, new, n)

    out: list[str] = []
    cursor = 0
    changed = 0
    for start, end in ranges:
        if cursor < start:
            segment = text[cursor:start]
            new_seg, n = _NUMBER_RE.subn(_humanize_one, segment)
            changed += _count_changed(segment, new_seg, n)
            out.append(new_seg)
        out.append(text[start:end])
        cursor = end
    if cursor < len(text):
        segment = text[cursor:]
        new_seg, n = _NUMBER_RE.subn(_humanize_one, segment)
        changed += _count_changed(segment, new_seg, n)
        out.append(new_seg)
    return "".join(out), changed


def _count_changed(before: str, after: str, n_total: int) -> int:
    """Count only matches that actually changed (year matches re-emit unchanged)."""
    if n_total == 0:
        return 0
    return n_total - sum(1 for m in _NUMBER_RE.finditer(before)
                         if len(m.group(1)) == 4 and 1900 <= int(m.group(1)) <= 2099)


def humanize_numbers(text: str) -> NumberResult:
    """Insert comma separators in bare 4+ digit integers, except years."""
    if not text:
        return NumberResult(text=text)
    ranges = protect.lexical_protected_ranges(text)
    new_text, changed = _apply_outside_protected(text, ranges)
    transformations: list[str] = []
    if changed:
        transformations.append(f"numbers:comma_separated:{changed}")
    return NumberResult(text=new_text, transformations=transformations)
