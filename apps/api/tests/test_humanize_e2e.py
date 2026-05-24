"""End-to-end regression tests for the humanize pipeline.

These tests use real-world inputs that previously broke the pipeline
(SEO meta-title blocks, list-headings with numbered prefixes, label lines
with parenthetical metadata, brand-name preservation) and assert the
post-humanization text still respects content structure.
"""

from __future__ import annotations

from humanizer.models import HumanizeRequest
from humanizer.pipeline import run_humanize


SEO_INPUT = """1. Flexible Earning Rules
Meta Title (48 characters): Create Flexible Earning Rules with Yotpo Loyalty

Meta Description (154 characters): Boost repeat purchases with Yotpo Loyalty. Design flexible earning rules that reward actions like reviews and referrals to drive long-term eCommerce growth.

2. Setup and Implementation
Meta Title (46 characters): Yotpo Loyalty Setup: Fast Implementation Guide

Meta Description (154 characters): Get your loyalty program live quickly. Our dedicated technical experts ensure a seamless setup and implementation for your custom Yotpo Loyalty structure.

3. Platform Migration
Meta Title (46 characters): Migrate to Yotpo Loyalty Without Losing Points

Meta Description (155 characters): Switching providers is easy with Yotpo Loyalty. Protect customer data and point balances while our technical experts manage your entire platform migration.

4. Loyalty Strategy & Scaling
Meta Title (43 characters): Build a Scaling Strategy with Yotpo Loyalty

Meta Description (152 characters): Evolve your retention program as your store grows. Partner with Yotpo Loyalty experts for ongoing technical support and proactive strategy optimization."""


def _humanize(text: str, strength: str = "medium") -> str:
    res = run_humanize(
        HumanizeRequest(text=text, language="en", strength=strength)  # type: ignore[arg-type]
    )
    return res.humanized_text


def test_numbered_headings_preserved_at_medium() -> None:
    # Layer 4 lowercases title-case headings (sentence case). The number
    # prefix and the first word stay; subsequent non-allowlist words go
    # lowercase. "Yotpo" stays capped (it's in PRESERVE_CAPS).
    out = _humanize(SEO_INPUT, "medium")
    for marker in (
        "1. Flexible earning rules",
        "2. Setup and implementation",
        "3. Platform migration",
        "4. Loyalty strategy & scaling",
    ):
        assert marker in out, f"missing heading: {marker!r}\n---\n{out}"


def test_numbered_headings_preserved_at_aggressive() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    for marker in (
        "1. Flexible earning rules",
        "2. Setup and implementation",
        "3. Platform migration",
        "4. Loyalty strategy & scaling",
    ):
        assert marker in out


def test_meta_labels_preserved() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    for label in (
        "Meta Title (48 characters):",
        "Meta Description (154 characters):",
        "Meta Title (46 characters):",
        "Meta Title (43 characters):",
        "Meta Description (155 characters):",
        "Meta Description (152 characters):",
    ):
        assert label in out, f"missing label: {label!r}"


def test_brand_name_preserved() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    # The brand appears 8 times in the source; require all of them.
    assert out.count("Yotpo Loyalty") == SEO_INPUT.count("Yotpo Loyalty")


def test_no_punchy_opener_on_headings_or_labels() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    bad_starts = ("So, ", "Still, ", "Then ", "But ", "And ")
    for line in out.splitlines():
        if line.startswith(bad_starts):
            # Acceptable only if it's a deep body sentence (no list/label start).
            raise AssertionError(
                f"line begins with punchy opener: {line!r}\nfull output:\n{out}"
            )


def test_no_em_dash_breaking_numbered_lists() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    for bad in ("1 — ", "2 — ", "3 — ", "4 — "):
        assert bad not in out, f"em-dash merged a list number: {bad!r}\n{out}"


def test_growth_and_point_not_swapped_to_nonsense() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    # "growth" and "point balances" must keep their semantics.
    assert "eCommerce growth" in out
    assert "point balances" in out


def test_parenthetical_metadata_protected() -> None:
    out = _humanize(SEO_INPUT, "aggressive")
    # All character-count parentheticals are unchanged.
    for paren in ("(48 characters)", "(154 characters)", "(46 characters)",
                  "(155 characters)", "(43 characters)", "(152 characters)"):
        assert paren in out


def test_short_single_sentence_label_line_does_not_gain_opener() -> None:
    text = "Meta Title (12 characters): Concise SEO Title For Search Engines"
    out = _humanize(text, "aggressive")
    # The body is a single phrase — no opener swap should fire.
    for bad in ("So, ", "Still, ", "Then ", "And ", "But "):
        assert bad not in out


def test_hebrew_heading_preserved() -> None:
    text = "כותרת ראשית\nזהו משפט גוף עם פועל וכמה מילים נוספות לדוגמה."
    res = run_humanize(
        HumanizeRequest(text=text, language="he", strength="aggressive")
    )
    assert "כותרת ראשית" in res.humanized_text
