"""AI-tell scrubber — Layer 2 of the proven humanization pipeline.

Eight categories of regex replacements that fire deterministically (always-on,
no probability skip) on text outside protected ranges (URLs, code, brand names).

Ported from the validated content-automation-unified pipeline (consistently
scores <10% AI on ZeroGPT). Adapted to plain text/markdown — no HTML.

Categories:
  - AI_VOCAB        : delve, navigate the, signpost transitions
  - COPULA          : "serves as a" → "is a"
  - REDUNDANT       : "in order to" → "to", "due to the fact that" → "because"
  - HEDGING         : "perhaps might" → "might"
  - SYCOPHANTIC     : "Great question!" → ""
  - CHATBOT         : "As an AI..." → ""
  - LANDSCAPE       : "in today's digital landscape" → ""
  - DIVE            : "let's dive in", "deep dive" → "let's look"

All patterns run case-insensitive. Cleanup pass collapses double spaces and
fixes whitespace before punctuation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from humanizer.engines import protect

Strength = Literal["light", "medium", "aggressive"]


@dataclass
class AITellResult:
    text: str
    transformations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pattern catalogue
# ---------------------------------------------------------------------------

# (pattern, replacement, tag) — `tag` is used in transformations for telemetry.
_AI_VOCAB: tuple[tuple[str, str, str], ...] = (
    # Signpost transitions
    (r"\bAdditionally,[ \t]+", "Also, ", "additionally_sentence"),
    (r"\bFurthermore,[ \t]+", "", "furthermore_sentence"),
    (r"\bMoreover,[ \t]+", "", "moreover_sentence"),
    (r"\bIn essence,[ \t]+", "", "in_essence"),
    (r"\bUltimately,[ \t]+", "", "ultimately_sentence"),
    (r"\bImportantly,[ \t]+", "", "importantly_sentence"),
    (r"\bIt is worth noting that[ \t]+", "", "worth_noting"),
    (r"\bIt's important to note that[ \t]+", "", "important_to_note"),
    (r"\bIt is important to note that[ \t]+", "Note that ", "it_is_important_to_note"),
    (r"\bIn conclusion,[ \t]+", "", "in_conclusion"),
    (r"\bTo summarize,[ \t]+", "", "to_summarize"),
    (r"\bIn summary,[ \t]+", "", "in_summary"),
    # Testament / overused verbs
    (r"\b(?:a|the)[ \t]+testament to\b", "evidence of", "testament_to"),
    (r"\bdelve into\b", "examine", "delve_into"),
    (r"\bdelves into\b", "examines", "delves_into"),
    (r"\bdelved into\b", "examined", "delved_into"),
    (r"\bnavigate the\b", "handle the", "navigate_the"),
    (r"\bnavigating the\b", "handling the", "navigating_the"),
    # Filler "actually" mid-sentence
    (r",[ \t]+actually,[ \t]+", ", ", "actually_mid"),
)

_COPULA: tuple[tuple[str, str, str], ...] = (
    (r"\bserves as a\b", "is a", "serves_as_a"),
    (r"\bserves as the\b", "is the", "serves_as_the"),
    (r"\bserves as an\b", "is an", "serves_as_an"),
    (r"\bacts as a\b", "is a", "acts_as_a"),
    (r"\bacts as an\b", "is an", "acts_as_an"),
    (r"\bfunctions as a\b", "is a", "functions_as_a"),
    (r"\bfunctions as an\b", "is an", "functions_as_an"),
)

_REDUNDANT: tuple[tuple[str, str, str], ...] = (
    (r"\bin order to\b", "to", "in_order_to"),
    (r"\bdue to the fact that\b", "because", "due_to_the_fact"),
    (r"\bin spite of the fact that\b", "although", "in_spite_of"),
    (r"\bat this point in time\b", "now", "at_this_point_in_time"),
    (r"\bat the present time\b", "now", "at_present_time"),
    (r"\bfor the purpose of\b", "to", "for_the_purpose_of"),
    (r"\bin the event that\b", "if", "in_the_event_that"),
    (r"\bwith the exception of\b", "except", "with_the_exception_of"),
    (r"\bprior to\b", "before", "prior_to"),
    (r"\bsubsequent to\b", "after", "subsequent_to"),
    (r"\bthe majority of\b", "most", "majority_of"),
    (r"\ba large number of\b", "many", "large_number_of"),
    (r"\ba significant number of\b", "many", "significant_number_of"),
)

_HEDGING: tuple[tuple[str, str, str], ...] = (
    (r"\bperhaps might\b", "might", "perhaps_might"),
    (r"\bcould potentially\b", "could", "could_potentially"),
    (r"\bmay possibly\b", "may", "may_possibly"),
    (r"\bvery unique\b", "unique", "very_unique"),
    (r"\bquite literally\b", "literally", "quite_literally"),
)

_SYCOPHANTIC: tuple[tuple[str, str, str], ...] = (
    (r"(?m)^[ \t]*Great question[!.][ \t]*", "", "great_question"),
    (r"(?m)^[ \t]*That's a great question[!.][ \t]*", "", "thats_a_great_question"),
    (r"\bI hope this helps[!.]?[ \t]*", "", "i_hope_this_helps"),
    (r"\bI hope this is helpful[!.]?[ \t]*", "", "i_hope_this_is_helpful"),
)

_CHATBOT: tuple[tuple[str, str, str], ...] = (
    (r"\bAs an AI(?:[ \t]+language[ \t]+model)?,?[ \t]*", "", "as_an_ai"),
    (r"\bI'm an AI(?:[ \t]+assistant)?,?[ \t]*", "", "im_an_ai"),
    (r"\bAs of my last knowledge update,?[ \t]*", "", "knowledge_update"),
    (r"\bbased on my training data,?[ \t]*", "", "training_data"),
)

# Landscape / world / era — the "in today's digital landscape" family.
_LANDSCAPE: tuple[tuple[str, str, str], ...] = (
    (
        r"\bin[ \t]+today's[ \t]+(?:digital|modern|fast[- ]paced|ever[- ]evolving)[ \t]+(?:landscape|world|era|marketplace)\b,?[ \t]*",
        "",
        "in_todays_landscape",
    ),
    (
        r"\bin[ \t]+the[ \t]+ever[- ]evolving[ \t]+(?:world|landscape)[ \t]+of\b[ \t]*",
        "in ",
        "ever_evolving_world",
    ),
    (r"\bin[ \t]+the[ \t]+world[ \t]+of\b[ \t]*", "in ", "in_the_world_of"),
    (r"\bthe[ \t]+digital[ \t]+landscape\b", "the market", "digital_landscape"),
    (r"\bthe[ \t]+modern[ \t]+landscape\b", "the market", "modern_landscape"),
)

# Generic deep-dive / let's-dive language.
_DIVE: tuple[tuple[str, str, str], ...] = (
    (r"\bLet's[ \t]+dive[ \t]+in[.!]?[ \t]*", "", "lets_dive_in"),
    (r"\blet's[ \t]+dive[ \t]+in[.!]?[ \t]*", "", "lets_dive_in_lc"),
    (r"\bLet's[ \t]+take[ \t]+a[ \t]+deep[ \t]+dive[ \t]+into\b", "Let's look at", "deep_dive_into"),
    (r"\ba[ \t]+deep[ \t]+dive[ \t]+into\b", "a look at", "a_deep_dive_into"),
)

_ALL_PATTERNS: tuple[tuple[str, str, str], ...] = (
    _AI_VOCAB + _COPULA + _REDUNDANT + _HEDGING + _SYCOPHANTIC + _CHATBOT
    + _LANDSCAPE + _DIVE
)

# Compile once at import time.
_COMPILED: tuple[tuple[re.Pattern[str], str, str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), r, tag) for p, r, tag in _ALL_PATTERNS
)


# ---------------------------------------------------------------------------
# Cleanup helpers
# ---------------------------------------------------------------------------

_DOUBLE_SPACE = re.compile(r"  +")
_SPACE_BEFORE_PUNCT = re.compile(r"[ \t]+([.,;:!?])")
_LEADING_LOWERCASE_AFTER_PERIOD = re.compile(r"([.!?][ \t]+)([a-z])")


def _cleanup(text: str) -> str:
    text = _DOUBLE_SPACE.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    # If a leading sentence opener got deleted, the next char may be lowercase.
    # Re-capitalize after sentence terminators.
    text = _LEADING_LOWERCASE_AFTER_PERIOD.sub(
        lambda m: m.group(1) + m.group(2).upper(), text
    )
    # Also re-capitalize text that now starts the string.
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


# ---------------------------------------------------------------------------
# Protected-range aware application
# ---------------------------------------------------------------------------


def _apply_outside_protected(
    text: str, fn, ranges: list[tuple[int, int]]
) -> str:
    """Run `fn(segment)` on each chunk of `text` not covered by `ranges`."""
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


def scrub_ai_tells(text: str, strength: Strength) -> AITellResult:
    """Apply the 8-category AI-tell scrub. Always-on (no probability skip).

    Light strength still runs the patterns: these are damning enough that
    they should never survive even a "gentle" pass. Strength affects
    other engines (lexical, structural), not this one.
    """
    if not text:
        return AITellResult(text=text)

    # Run inside heading bodies too — heading lines like "Why X In Today's
    # Digital Landscape" are exactly where AI tells live. Brand-name runs and
    # URLs/code remain protected via the rest of the range set.
    ranges = protect.lexical_protected_ranges(text, protect_headings=False)
    transforms: list[str] = []

    def _transform(segment: str) -> str:
        out = segment
        for pat, repl, tag in _COMPILED:
            new_out, n = pat.subn(repl, out)
            if n:
                transforms.append(f"ai_tells:{tag}:{n}")
                out = new_out
        return out

    result = _apply_outside_protected(text, _transform, ranges)
    result = _cleanup(result)
    return AITellResult(text=result, transformations=transforms)
