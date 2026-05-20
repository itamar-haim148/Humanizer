"""Watermark cleaner.

Combines ideas from:
  - ByteMastermind/Markless-GPT (MIT) — zero-width / NBSP stripping
  - cronos3k/Text-Stealth-Watermark-Cleaner-Detector — invisible Unicode,
    control chars, homoglyph detection via NFKC delta.

Pure stdlib; no dependencies.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from humanizer.models import CleaningReport, WatermarkFinding

# ---------------------------------------------------------------------------
# Codepoint tables
# ---------------------------------------------------------------------------

# Strip entirely (replace with empty string).
#
# Set unified from:
#  * ByteMastermind/Markless-GPT (zero-width family)
#  * cronos3k/Text-Stealth-Watermark-Cleaner-Detector (bidi marks, bidi
#    override, invisible math operators, soft hyphen)
_STRIP_CHARS: dict[str, str] = {
    "\u200B": "ZERO WIDTH SPACE",
    "\u200C": "ZERO WIDTH NON-JOINER",
    "\u200D": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\u180E": "MONGOLIAN VOWEL SEPARATOR",
    "\u00AD": "SOFT HYPHEN",
    "\u202A": "LEFT-TO-RIGHT EMBEDDING",
    "\u202B": "RIGHT-TO-LEFT EMBEDDING",
    "\u202C": "POP DIRECTIONAL FORMATTING",
    "\u202D": "LEFT-TO-RIGHT OVERRIDE",
    "\u202E": "RIGHT-TO-LEFT OVERRIDE",
    "\u2061": "FUNCTION APPLICATION (invisible)",
    "\u2062": "INVISIBLE TIMES",
    "\u2063": "INVISIBLE SEPARATOR",
    "\u2064": "INVISIBLE PLUS",
}

# LRM / RLM are kept as findings only — they are sometimes legitimate in
# Hebrew documents for mixed-script rendering of numerals and punctuation.
# Removing them silently could break the user's intent.
_REPORT_ONLY_CHARS: dict[str, str] = {
    "\u200E": "LEFT-TO-RIGHT MARK",
    "\u200F": "RIGHT-TO-LEFT MARK",
}

# Normalize non-standard spaces to U+0020
_NORMALIZE_SPACES: dict[str, str] = {
    "\u00A0": "NO-BREAK SPACE",
    "\u202F": "NARROW NO-BREAK SPACE",
    "\u2007": "FIGURE SPACE",
    "\u2008": "PUNCTUATION SPACE",
    "\u2009": "THIN SPACE",
    "\u200A": "HAIR SPACE",
    "\u205F": "MEDIUM MATHEMATICAL SPACE",
    "\u3000": "IDEOGRAPHIC SPACE",
}

BOM = "\uFEFF"


def _codepoint(ch: str) -> str:
    return f"U+{ord(ch):04X}"


def _is_control(ch: str) -> bool:
    cat = unicodedata.category(ch)
    if cat not in ("Cc", "Cf"):
        return False
    return ch not in ("\n", "\t", "\r")


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class CleanResult:
    cleaned_text: str
    findings: list[WatermarkFinding] = field(default_factory=list)
    removed_count: int = 0
    normalized_count: int = 0

    def to_report(self) -> CleaningReport:
        return CleaningReport(
            removed_count=self.removed_count,
            normalized_count=self.normalized_count,
            findings=self.findings,
        )


# ---------------------------------------------------------------------------
# Detection-only (no mutation)
# ---------------------------------------------------------------------------


def detect_only(text: str) -> list[WatermarkFinding]:
    """Scan text for invisible/suspicious characters; do not mutate."""
    findings: list[WatermarkFinding] = []
    for i, ch in enumerate(text):
        if ch in _STRIP_CHARS:
            findings.append(
                WatermarkFinding(
                    kind="zero_width",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_STRIP_CHARS[ch],
                )
            )
        elif ch in _REPORT_ONLY_CHARS:
            findings.append(
                WatermarkFinding(
                    kind="bidi_mark",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_REPORT_ONLY_CHARS[ch] + " (kept — may be legitimate)",
                )
            )
        elif ch == BOM:
            findings.append(
                WatermarkFinding(
                    kind="bom",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note="UTF-8 BOM",
                )
            )
        elif ch == "\u00A0":
            findings.append(
                WatermarkFinding(
                    kind="nbsp",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note="NO-BREAK SPACE",
                )
            )
        elif ch in _NORMALIZE_SPACES:
            findings.append(
                WatermarkFinding(
                    kind="non_standard_space",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_NORMALIZE_SPACES[ch],
                )
            )
        elif _is_control(ch):
            findings.append(
                WatermarkFinding(
                    kind="control_char",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=unicodedata.name(ch, "UNKNOWN"),
                )
            )

    # Homoglyph hint via NFKC delta on ASCII-mostly text
    nfkc = unicodedata.normalize("NFKC", text)
    if nfkc != text:
        for i, (a, b) in enumerate(zip(text, nfkc)):
            if a != b and not a.isspace():
                findings.append(
                    WatermarkFinding(
                        kind="homoglyph",
                        char=a,
                        codepoint=_codepoint(a),
                        index=i,
                        note=f"NFKC → {_codepoint(b)} ({b})",
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Main cleaner
# ---------------------------------------------------------------------------


def clean(text: str) -> CleanResult:
    """Strip invisible chars, normalize whitespace, apply NFKC. Returns
    `CleanResult` with detailed findings."""
    if not text:
        return CleanResult(cleaned_text="")

    findings: list[WatermarkFinding] = []
    removed = 0
    normalized = 0
    starts_with_bom = text.startswith(BOM)
    out: list[str] = []

    for i, ch in enumerate(text):
        if ch == BOM:
            # Preserve only when it's at index 0.
            if i == 0 and starts_with_bom:
                out.append(ch)
            else:
                removed += 1
                findings.append(
                    WatermarkFinding(
                        kind="bom",
                        char=ch,
                        codepoint=_codepoint(ch),
                        index=i,
                        note="BOM not at start; stripped",
                    )
                )
            continue
        if ch in _STRIP_CHARS:
            removed += 1
            findings.append(
                WatermarkFinding(
                    kind="zero_width",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_STRIP_CHARS[ch],
                )
            )
            continue
        if ch in _NORMALIZE_SPACES:
            kind: Literal["nbsp", "non_standard_space"] = (
                "nbsp" if ch == "\u00A0" else "non_standard_space"
            )
            normalized += 1
            findings.append(
                WatermarkFinding(
                    kind=kind,
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_NORMALIZE_SPACES[ch],
                )
            )
            out.append(" ")
            continue
        if ch in _REPORT_ONLY_CHARS:
            # Preserve LRM/RLM — may be legitimate in Hebrew docs. Must be
            # checked BEFORE _is_control because LRM/RLM are category Cf and
            # would otherwise be stripped.
            findings.append(
                WatermarkFinding(
                    kind="bidi_mark",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=_REPORT_ONLY_CHARS[ch] + " (kept — may be legitimate)",
                )
            )
            out.append(ch)
            continue
        if _is_control(ch):
            removed += 1
            findings.append(
                WatermarkFinding(
                    kind="control_char",
                    char=ch,
                    codepoint=_codepoint(ch),
                    index=i,
                    note=unicodedata.name(ch, "UNKNOWN"),
                )
            )
            continue
        out.append(ch)

    interim = "".join(out)
    # Detect runs of 2+ consecutive ASCII spaces/tabs as a watermark signal
    # (cronos3k pattern). Report-only — collapsing whitespace is a stylistic
    # decision left to the pipeline's structural engines.
    #
    # Scan the *original* text so indices match the indices of other findings
    # (which use `enumerate(text)`). NBSP/thin-space sequences are already
    # surfaced as `nbsp` / `non_standard_space` findings, so restricting to
    # raw ASCII space/tab avoids double-reporting.
    for m in re.finditer(r"[ \t]{2,}", text):
        first = m.group(0)[:1]
        findings.append(
            WatermarkFinding(
                kind="excessive_whitespace",
                char=first,
                codepoint=_codepoint(first),
                index=m.start(),
                note=f"{m.end() - m.start()} consecutive whitespace chars",
            )
        )
    # NFKC normalize; record homoglyph deltas.
    nfkc = unicodedata.normalize("NFKC", interim)
    if nfkc != interim:
        nfkc_findings = _homoglyph_findings(interim, nfkc)
        findings.extend(nfkc_findings)
    cleaned = nfkc

    return CleanResult(
        cleaned_text=cleaned,
        findings=findings,
        removed_count=removed,
        normalized_count=normalized,
    )


def _homoglyph_findings(before: str, after: str) -> list[WatermarkFinding]:
    """Report only char-for-char swaps; ignore length-changing decompositions."""
    if len(before) != len(after):
        return []
    res: list[WatermarkFinding] = []
    for i, (a, b) in enumerate(zip(before, after)):
        if a != b and not a.isspace():
            res.append(
                WatermarkFinding(
                    kind="homoglyph",
                    char=a,
                    codepoint=_codepoint(a),
                    index=i,
                    note=f"NFKC → {_codepoint(b)} ({b})",
                )
            )
    return res
