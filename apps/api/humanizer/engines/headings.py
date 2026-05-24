"""Heading sentence-case — Layer 4.

LLM output Title-Cases every heading ("Why This Matters For Your Business").
Real human writers use sentence case ("Why this matters for your business").
This is a small but reliable AI-tell fix.

Strategy per heading line:
  - First word stays as-is (sentence opener).
  - Words in PRESERVE_CAPS allowlist stay as-is (AI, SEO, ChatGPT, …).
  - Pure-ALL-CAPS short tokens stay as-is (acronyms we didn't list).
  - Everything else → lowercase.
  - After a colon, lowercase the next word too (sub-heading start).

EN only. Hebrew has no case — skipped entirely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from humanizer.engines import protect

# Brands, acronyms, and proper nouns that must keep their casing inside a
# heading. Compared case-insensitively against the stripped token; the
# original casing from this set is what gets emitted.
PRESERVE_CAPS: tuple[str, ...] = (
    # AI / search acronyms
    "AI", "SEO", "GEO", "AEO", "FAQ", "PDP", "SKU", "ROI", "API", "URL",
    "TL;DR", "CEO", "CTO", "CMO", "CFO", "COO", "B2B", "B2C", "SaaS",
    "USA", "UK", "EU", "UAE", "UN", "EU",
    # AI vendors / products
    "ChatGPT", "Gemini", "Claude", "OpenAI", "Anthropic", "Perplexity",
    "Google", "Meta", "Microsoft", "Apple", "Amazon", "Yotpo", "Shopify",
    "WordPress", "GitHub", "GitLab", "Slack", "Notion", "Figma",
    # Web / tech
    "HTML", "CSS", "JSON", "XML", "HTTP", "HTTPS", "REST", "GraphQL",
    "iOS", "macOS", "Android", "Linux", "Windows",
    # Other common proper nouns
    "Q1", "Q2", "Q3", "Q4",
)

_PRESERVE_LOOKUP: dict[str, str] = {tok.lower(): tok for tok in PRESERVE_CAPS}

# Hash-prefix splitter: capture leading "#" markers + spaces so we can keep them.
_HEADING_PREFIX_RE = re.compile(r"^(\s*#{1,6}\s+)(.*)$")

# Hebrew character range — if present, skip the line.
_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")

# Word-ish token matcher: keeps punctuation around words intact.
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*")


@dataclass
class HeadingResult:
    text: str
    transformations: list[str] = field(default_factory=list)


def _lower_token(tok: str, *, is_first: bool) -> str:
    """Lowercase `tok` unless it's in the allowlist, an acronym, or sentence-initial."""
    if not tok:
        return tok
    # Allowlist (case-insensitive lookup, original casing wins).
    key = tok.lower()
    if key in _PRESERVE_LOOKUP:
        return _PRESERVE_LOOKUP[key]
    # Pure ALL-CAPS short token (2-5 chars) → assume acronym, keep.
    if 2 <= len(tok) <= 5 and tok.isupper():
        return tok
    # Word containing a digit (e.g., "iPhone15") → leave alone.
    if any(ch.isdigit() for ch in tok):
        return tok
    if is_first:
        # Sentence opener: keep current capitalisation pattern.
        return tok
    # Lowercase, but preserve internal apostrophes / hyphens.
    return tok.lower()


def _sentence_case_body(body: str) -> str:
    """Apply sentence-case to a single heading body string."""
    if not body.strip():
        return body
    # Track "is this the first word of the current sentence-segment?"
    # A segment is the start of the heading OR right after ":".
    first_pending = True
    out: list[str] = []
    last = 0
    for m in _WORD_RE.finditer(body):
        out.append(body[last:m.start()])
        tok = m.group(0)
        out.append(_lower_token(tok, is_first=first_pending))
        last = m.end()
        first_pending = False
    out.append(body[last:])
    result = "".join(out)
    # After ":" followed by space + word, lowercase that next word.
    # (Apply iteratively for headings like "Methods: Part One: Schema".)
    def _colon_lower(match: re.Match[str]) -> str:
        prefix = match.group(1)
        word = match.group(2)
        # Don't touch if it's in the allowlist.
        if word.lower() in _PRESERVE_LOOKUP:
            return prefix + _PRESERVE_LOOKUP[word.lower()]
        if 2 <= len(word) <= 5 and word.isupper():
            return prefix + word
        return prefix + word[0].lower() + word[1:]

    result = re.sub(r"(:\s+)([A-Z][A-Za-z'\-]*)", _colon_lower, result)
    return result


def sentence_case_headings(text: str, language: str = "en") -> HeadingResult:
    """Lower-case Title-Case headings; preserve acronyms and brand names.

    Operates on:
      - Markdown ATX headings: lines starting with `#`/`##`/...
      - Implicit headings: short lines (<=8 words) without terminal punctuation,
        as identified by `protect.classify_lines()`.

    Hebrew text is skipped entirely.
    """
    if not text or language != "en":
        return HeadingResult(text=text)

    lines = protect.classify_lines(text)
    out_chunks: list[str] = []
    changed_count = 0
    cursor = 0
    for line in lines:
        # Append the gap (only the newline between lines).
        if cursor < line.start:
            out_chunks.append(text[cursor:line.start])
        original = line.text
        if line.kind != "heading":
            out_chunks.append(original)
            cursor = line.end
            continue
        # Skip if line contains Hebrew.
        if _HEBREW_RE.search(original):
            out_chunks.append(original)
            cursor = line.end
            continue
        # Split off leading "# " marker if present.
        m = _HEADING_PREFIX_RE.match(original)
        if m:
            prefix, body = m.group(1), m.group(2)
        else:
            # Implicit heading: preserve leading whitespace.
            stripped_lead = len(original) - len(original.lstrip())
            prefix = original[:stripped_lead]
            body = original[stripped_lead:]
        new_body = _sentence_case_body(body)
        new_line = prefix + new_body
        if new_line != original:
            changed_count += 1
        out_chunks.append(new_line)
        cursor = line.end
    if cursor < len(text):
        out_chunks.append(text[cursor:])

    transformations: list[str] = []
    if changed_count:
        transformations.append(f"headings:sentence_case:{changed_count}")
    return HeadingResult(text="".join(out_chunks), transformations=transformations)
