"""Post-LLM polish — pattern fixes for typical Gemini-style rewrites.

Runs immediately after the LLM in the LLM-mode pipeline, before the
lexical and structural passes. Targets three failure modes that pure
dictionary substitution can't reach:

  1. Semicolon parallel-pivot ("It isn't just about X; it's about Y") —
     a parallel-construction tell. Split into two sentences.
  2. Redundant intensifier adjective stripping in safe contexts only
     ("a genuine reason" → "a reason"). Constrained to a, an, the, this,
     that, these, those + adjective + lowercase noun, so we never strip
     before a proper noun.
  3. Empty contrastive frames ("It's not just X; it's Y" → "It's Y").
     The "not just X; Y" construction is a classic LLM tell because the
     contrast is rarely informative.

Each transform is conservative and preserves meaning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

Strength = Literal["light", "medium", "aggressive"]


@dataclass
class PostLLMResult:
    text: str
    transformations: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pattern 1: semicolon parallel-pivot
#
# Examples this matches (case-insensitive, within one sentence):
#   "It isn't just about making a sale; it's about building loyalty."
#   "X is not just Y; this is Z."
#   "...not only X; this Y."
#
# Strategy: chop at the semicolon, drop the contrastive frame on the
# left ("isn't just about", "is not just", "not only"), and rebuild as
# two sentences. We keep the right-hand clause as the carrier because
# that's where the LLM hid the real claim.
# ---------------------------------------------------------------------------

_PIVOT_LEFT = re.compile(
    r"\b(?:it|this|that)\s+"
    r"(?:isn't|is\s+not|wasn't|was\s+not|won't\s+be|will\s+not\s+be)\s+"
    r"(?:just|only|merely|simply|all)\s+"
    r"(?:about\s+|a\s+matter\s+of\s+)?",
    re.IGNORECASE,
)

_SEMICOLON_PIVOT_RE = re.compile(
    # `[A-Za-z]` anchors the left clause at a letter — this way the match
    # never starts at the prior sentence's period or at whitespace, which
    # would otherwise leak punctuation into the substituted clause.
    r"([A-Za-z][^.!?\n;]{7,}?)"          # left clause (≥8 chars total)
    r";\s+"                              # semicolon boundary
    r"(it|this|that)('s|\s+is)\s+"      # right pronoun + copula
    r"(?:about\s+|all\s+about\s+|really\s+about\s+)?"
    r"([^.!?\n]+[.!?])",                # right clause + terminator
    re.IGNORECASE,
)


def _semicolon_split(m: re.Match[str]) -> str:
    """Split 'X; it Y' into 'X. It Y.' (drops contrastive frame on X)."""
    left = m.group(1).rstrip(" ,;")
    pronoun = m.group(2)
    contraction = m.group(3)
    right = m.group(4)

    # Drop "it isn't just about" / "this is not just" framings from the
    # left clause. If the entire left was the frame, fall back to the
    # right clause alone with the contrastive pivot removed.
    left_stripped = _PIVOT_LEFT.sub("", left).strip(" ,;")
    if not left_stripped:
        # The whole left clause was filler — emit just the right side.
        return f"{pronoun.capitalize()}{contraction} {right}"

    # Capitalize the first char (the left clause is now a new sentence).
    left_stripped = left_stripped[:1].upper() + left_stripped[1:]
    # Terminate the left properly.
    if not left_stripped.endswith((".", "!", "?")):
        left_stripped += "."
    return f"{left_stripped} {pronoun.capitalize()}{contraction} {right}"


# ---------------------------------------------------------------------------
# Deterministic Gemini-tell phrase substitutions
#
# These run BEFORE the lexical engine (which is probabilistic at <100%
# ratio). The phrases here are damning enough AI signatures that we
# always want them gone — no random skips. Sorted longest-first by the
# polish() loop so overlapping prefixes resolve correctly.
# ---------------------------------------------------------------------------

_DETERMINISTIC_SUBS: tuple[tuple[str, str], ...] = (
    # "By putting these rules to work" — Gemini's go-to anti-leverage rephrase.
    ("by putting these rules to work", "with these rules"),
    ("by putting this to work", "with this"),
    ("putting these rules to work", "with these rules"),
    # "Actions/things that actually X" — empty intensifier between noun and verb.
    ("actions that actually ", "actions that "),
    ("things that actually ", "things that "),
    ("people who actually ", "people who "),
    ("ways that actually ", "ways that "),
    ("steps that actually ", "steps that "),
    # "Is done in a way that is X" → "is X". Longest first so this beats
    # the shorter " in a way that " rewrite below.
    ("is done in a way that is", "is"),
    ("are done in a way that is", "are"),
    ("done in a way that is", ""),
    ("done in a way that", ""),
    (" in a way that is ", " "),
    (" in a way that ", " that "),
    # "Structure for a cycle of" / "build a structure for" — paired pads.
    ("build a structure for a cycle of", "build a cycle of"),
    ("structure for a cycle of", "cycle of"),
    ("build a structure for", "build"),
    # "A quick sale" / "a quick win" — generic LLM padding before common
    # business nouns. Targeted (not the whole "quick" adjective) so we
    # don't break "a quick fix" or "a quick question".
    ("a quick sale", "a sale"),
    ("a quick win", "a win"),
    ("quick sales", "sales"),
)


def _apply_deterministic_subs(text: str) -> tuple[str, list[str]]:
    """Apply each phrase ALWAYS (no probability). Returns (text, transforms).

    Preserves leading capitalization: if the matched phrase started with
    an uppercase letter (sentence-initial), the replacement is also
    capitalized. This avoids "By putting these rules to work, you build…"
    becoming "with these rules, you build…" mid-paragraph.
    """
    out = text
    transforms: list[str] = []
    for phrase, replacement in sorted(
        _DETERMINISTIC_SUBS, key=lambda kv: -len(kv[0])
    ):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)

        def _sub(m: re.Match[str], r: str = replacement) -> str:
            original = m.group(0)
            if r and original[:1].isupper() and r[:1].isalpha():
                return r[:1].upper() + r[1:]
            return r

        new_out, n = pattern.subn(_sub, out)
        if n:
            transforms.append(f"post_llm:phrase:{phrase!r}:{n}")
            out = new_out
    return out, transforms


# ---------------------------------------------------------------------------
# Pattern 2: redundant intensifier adjectives in safe determiner contexts
#
# Only fire when an empty modifier sits between a determiner and a
# lowercase common noun. This way we never strip "real" in "the Real
# Madrid story" (proper noun) or "genuine" in "Genuine Parts Co."
# ---------------------------------------------------------------------------

_INTENSIFIER = r"genuine|real|actual|truly|true|specific|deeper|deep"

_DETERMINER_ADJ_RE = re.compile(
    rf"\b(?P<det>a|an|the|this|that|these|those|our|your|their|its|my)\s+"
    rf"(?P<adj>{_INTENSIFIER})\s+"
    # Lookahead is case-sensitive ((?-i:...)) so it only matches lowercase
    # common nouns. This protects proper-noun runs like "Real Madrid".
    r"(?=(?-i:[a-z][a-z'\-]{2,})\b)",
    re.IGNORECASE,
)


def _strip_intensifier(m: re.Match[str]) -> str:
    det = m.group("det")
    return f"{det} "


# ---------------------------------------------------------------------------
# Filler transitions — sentence-initial connectives that mark LLM prose.
# Run at sentence-start position only (after . ! ? or paragraph start).
# ---------------------------------------------------------------------------

_FILLER_TRANSITIONS: tuple[tuple[str, str], ...] = (
    (r"(?m)^Furthermore,[ \t]+", ""),
    (r"(?m)^Moreover,[ \t]+", ""),
    (r"(?m)^Additionally,[ \t]+", "Also, "),
    (r"(?<=[.!?])[ \t]+Furthermore,[ \t]+", " "),
    (r"(?<=[.!?])[ \t]+Moreover,[ \t]+", " "),
    (r"(?<=[.!?])[ \t]+Additionally,[ \t]+", " Also, "),
    # "The results speak for themselves" can be terminated by any of . , : ; ! ?
    # We consume the terminator + trailing horizontal whitespace (not newlines).
    (r"\bThe results speak for themselves[.,:;!?][ \t]*", ""),
    (r"\bAt the end of the day,?[ \t]*", ""),
    (r"\bBut here'?s the thing,?[ \t]*", ""),
    (r"\bAt the heart of it,?[ \t]*", ""),
    (r"\bWhen all is said and done,?[ \t]*", ""),
)

_FILLER_COMPILED: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), r) for p, r in _FILLER_TRANSITIONS
)


# ---------------------------------------------------------------------------
# Hacky LLM phrases — overused metaphors and AI-staple constructions.
# ---------------------------------------------------------------------------

_HACKY_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bthe digital landscape\b", "the market"),
    (r"\bthe modern landscape\b", "the market"),
    (r"\bthe current landscape\b", "the market"),
    (r"\bin the ever[- ]evolving world of\b", "in"),
    (r"\bin the ever[- ]changing world of\b", "in"),
    (r"\bin today'?s fast[- ]paced world\b", "today"),
    (r"\bin the world of\b", "in"),
    (r"\bnavigate the complexities of\b", "work through"),
    (r"\bnavigate the world of\b", "work in"),
    # The stealth/perplexity pass can rewrite "navigate" → "handle". Catch the
    # post-swap form too so the AI-tell phrasing doesn't survive.
    (r"\bhandle the complexities of\b", "work through"),
    (r"\bwork through the complexities of\b", "work through"),
    (r"\bharness the power of\b", "use"),
    (r"\bunleash the power of\b", "use"),
    (r"\bunlock the potential of\b", "use"),
    (r"\bunlock the full potential of\b", "use"),
    (r"\bbridge the gap between\b", "connect"),
    (r"\bpave the way for\b", "enable"),
    (r"\bopen the door to\b", "lead to"),
    (r"\btake your\s+(\w+)\s+to the next level\b", r"improve your \1"),
    (r"\ba game[- ]changer\b", "important"),
    (r"\ba paradigm shift\b", "a shift"),
    (r"\bin order to better\b", "to better"),
    (r"\bcutting[- ]edge\b", "modern"),
    (r"\bstate[- ]of[- ]the[- ]art\b", "modern"),
    (r"\bbest[- ]in[- ]class\b", "leading"),
)

_HACKY_COMPILED: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(p, re.IGNORECASE), r) for p, r in _HACKY_REPLACEMENTS
)


# Missing space after comma (common Gemini tell when emitting code-adjacent text)
_COMMA_NO_SPACE_RE = re.compile(r",(?=[A-Za-z])")


def _apply_compiled_subs(
    text: str,
    compiled: tuple[tuple[re.Pattern[str], str], ...],
    tag: str,
) -> tuple[str, list[str]]:
    out = text
    transforms: list[str] = []
    for pat, repl in compiled:
        new_out, n = pat.subn(repl, out)
        if n:
            transforms.append(f"post_llm:{tag}:{n}")
            out = new_out
    return out, transforms


def _cleanup_post(text: str) -> str:
    """Collapse double spaces and re-capitalize after period deletions."""
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    # Re-capitalize sentence starts whose openers we just deleted.
    text = re.sub(
        r"([.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------


def polish(text: str, strength: Strength) -> PostLLMResult:
    """Apply post-LLM patterns. No-op at strength='light'."""
    if not text or strength == "light":
        return PostLLMResult(text=text)

    transformations: list[str] = []
    out = text

    # 0. Deterministic Gemini-tell phrase substitutions.
    out, det_transforms = _apply_deterministic_subs(out)
    transformations.extend(det_transforms)

    # 1. Filler-transition strip.
    out, t = _apply_compiled_subs(out, _FILLER_COMPILED, "filler")
    transformations.extend(t)

    # 2. Hacky LLM-phrase substitutions.
    out, t = _apply_compiled_subs(out, _HACKY_COMPILED, "hacky")
    transformations.extend(t)

    # 3. Missing-space-after-comma fix.
    new_out, n = _COMMA_NO_SPACE_RE.subn(", ", out)
    if n:
        transformations.append(f"post_llm:comma_space:{n}")
        out = new_out

    # 4. Semicolon pivot → two sentences
    new_out, n = _SEMICOLON_PIVOT_RE.subn(_semicolon_split, out)
    if n:
        transformations.append(f"post_llm:semicolon_pivot:{n}")
        out = new_out

    # 5. Strip redundant intensifier adjectives (aggressive + medium)
    new_out, n = _DETERMINER_ADJ_RE.subn(_strip_intensifier, out)
    if n:
        transformations.append(f"post_llm:strip_intensifier:{n}")
        out = new_out

    # 6. Final cleanup pass (whitespace + recapitalize).
    out = _cleanup_post(out)

    return PostLLMResult(text=out, transformations=transformations)
