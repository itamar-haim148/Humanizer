"""Unit tests for the post-LLM polish engine.

These cover the three pattern families the engine targets:
  1. Semicolon parallel-pivot ("It isn't just X; it's Y")
  2. Empty intensifier adjectives ("a genuine reason" → "a reason")
  3. "is done in a way that is" padding removal
"""

from __future__ import annotations

import pytest

from humanizer.engines.post_llm_polish import polish


# ---------------------------------------------------------------------------
# Semicolon-pivot splitting
# ---------------------------------------------------------------------------


def test_semicolon_pivot_basic() -> None:
    src = "It isn't just about making a sale; it's about building loyalty."
    out = polish(src, "aggressive").text
    # The contrastive frame should be gone.
    assert "isn't just" not in out.lower()
    assert "not just" not in out.lower()
    # The real claim survives.
    assert "building loyalty" in out


def test_semicolon_pivot_with_left_content() -> None:
    """If the left has real content beyond the pivot frame, keep it."""
    src = (
        "Customer engagement matters, and it is not just about clicks; "
        "this is about long-term value."
    )
    out = polish(src, "aggressive").text
    assert "long-term value" in out
    assert "not just" not in out.lower()


def test_semicolon_pivot_not_triggered_without_pronoun() -> None:
    src = "We launched on Tuesday; the rollout was uneventful."
    out = polish(src, "aggressive").text
    # No pivot frame, so the engine should leave it alone.
    assert out == src


# ---------------------------------------------------------------------------
# Intensifier stripping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "src,expected_fragment",
    [
        ("Customers need a genuine reason to act.", "a reason"),
        ("They built a real relationship.", "a relationship"),
        ("Reward the specific behaviors.", "the behaviors"),
        ("Avoid the actual fact entirely.", "the fact"),
        ("Our truly customers deserve more.", "Our customers"),
    ],
)
def test_intensifier_stripping(src: str, expected_fragment: str) -> None:
    out = polish(src, "aggressive").text
    assert expected_fragment in out


def test_intensifier_preserved_before_proper_noun() -> None:
    """Don't strip 'Real' when followed by a proper noun like Real Madrid."""
    src = "The real Madrid headquarters opened in 1902."
    out = polish(src, "aggressive").text
    # 'Madrid' starts with capital M, so the regex (which only matches
    # before lowercase common nouns) should leave it alone.
    assert "real Madrid" in out


def test_intensifier_preserved_at_light_strength() -> None:
    src = "Customers want a genuine reason."
    out = polish(src, "light").text
    assert out == src


# ---------------------------------------------------------------------------
# "is done in a way that is..." padding
# ---------------------------------------------------------------------------


def test_done_in_a_way_collapsed() -> None:
    src = "It is done in a way that is entirely unique to your business."
    out = polish(src, "aggressive").text
    assert "in a way" not in out
    assert "It is entirely unique to your business" in out


def test_done_in_a_way_case_insensitive() -> None:
    src = "This Is Done In A Way That Is unmatched."
    out = polish(src, "aggressive").text
    assert "in a way" not in out.lower()


# ---------------------------------------------------------------------------
# Transformations report
# ---------------------------------------------------------------------------


def test_transformations_recorded() -> None:
    src = (
        "It isn't just about a quick sale; it's about a real connection. "
        "This is done in a way that is unique."
    )
    result = polish(src, "aggressive")
    joined = " ".join(result.transformations)
    assert "post_llm:semicolon_pivot" in joined
    assert "post_llm:strip_intensifier" in joined
    # The "is done in a way that is" deterministic phrase fires.
    assert "post_llm:phrase" in joined


def test_light_strength_noop() -> None:
    src = "It isn't just about X; it's about Y. A genuine reason."
    out = polish(src, "light")
    assert out.text == src
    assert out.transformations == []


# ---------------------------------------------------------------------------
# End-to-end on actual Gemini output that previously scored 60% AI
# ---------------------------------------------------------------------------


def test_real_gemini_yotpo_output_gets_scrubbed() -> None:
    """The exact text Gemini produced in production. Verify every known
    AI tell from the original output is removed by the full post-LLM
    pipeline."""
    from humanizer.engines import cleaner as clnr
    from humanizer.engines import lexical_en, structural

    gemini = (
        "Customers need a genuine reason to stick around, and standard "
        "points programs often fall flat. Yotpo Loyalty lets you reward "
        "the specific behaviors that matter most to your business.\n\n"
        "By putting these rules to work, you build a structure for a "
        "cycle of engagement that encourages repeat purchases and "
        "maximizes customer lifetime value. It is done in a way that is "
        "entirely unique to your customer base and business model.\n\n"
        "To drive long-term value for your store, you need to give "
        "customers points for actions that actually deepen their "
        "connection to your brand. It isn't just about making a quick "
        "sale; it's about building a real relationship."
    )

    t = clnr.clean(gemini).cleaned_text
    t = polish(t, "aggressive").text
    t = lexical_en.humanize_lexical(t, "aggressive").text
    t = structural.humanize_structural(t, "en", "aggressive")
    t = clnr.clean(t).cleaned_text

    lower = t.lower()
    # Adjective-padding tells
    assert "a genuine reason" not in lower
    assert "the specific behaviors" not in lower
    assert "a real relationship" not in lower
    assert "a quick sale" not in lower or "a sale" in lower
    # Structural tells
    assert "by putting these rules to work" not in lower
    assert "structure for a cycle" not in lower
    assert "in a way that is" not in lower
    # "actions that actually" empty-intensifier
    assert "that actually deepen" not in lower
    # Semicolon-pivot must be broken
    assert "isn't just about making a quick sale; it's" not in lower
