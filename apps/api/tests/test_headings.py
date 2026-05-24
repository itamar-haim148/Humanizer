"""Tests for Layer 4 sentence-case headings."""

from __future__ import annotations

from humanizer.engines.headings import sentence_case_headings


def test_markdown_h1_sentence_cased() -> None:
    out = sentence_case_headings("# Why This Matters For Your Business").text
    assert out == "# Why this matters for your business"


def test_markdown_h2_sentence_cased() -> None:
    out = sentence_case_headings("## How To Build A Loyalty Program").text
    assert out == "## How to build a loyalty program"


def test_preserve_caps_allowlist_kept() -> None:
    out = sentence_case_headings("# How To Use ChatGPT For SEO").text
    assert "ChatGPT" in out
    assert "SEO" in out
    assert "for SEO" in out


def test_yotpo_brand_preserved() -> None:
    out = sentence_case_headings("# Setup Yotpo Loyalty Quickly").text
    assert "Yotpo" in out


def test_implicit_heading_short_line_no_terminator() -> None:
    out = sentence_case_headings("Setup and Implementation").text
    assert out == "Setup and implementation"


def test_implicit_heading_left_alone_when_terminated() -> None:
    text = "Setup is required for the system to work."
    assert sentence_case_headings(text).text == text


def test_acronym_preserved() -> None:
    out = sentence_case_headings("# Setting Up Your API Endpoint").text
    assert "API" in out
    assert "endpoint" in out


def test_hebrew_skipped() -> None:
    text = "# כותרת ראשית בעברית"
    assert sentence_case_headings(text).text == text


def test_hebrew_via_language_param() -> None:
    """Even an EN-looking heading shouldn't be touched when language='he'."""
    text = "# Title Case Here"
    assert sentence_case_headings(text, language="he").text == text


def test_colon_subhead_lowercased() -> None:
    out = sentence_case_headings("# Methods: Improve Schema Output").text
    assert "methods: improve" in out.lower()


def test_numbered_heading_first_word_kept() -> None:
    out = sentence_case_headings("1. Flexible Earning Rules").text
    assert out == "1. Flexible earning rules"


def test_prose_lines_untouched() -> None:
    text = "This Is A Title.\nAnd this is body text with terminator."
    out = sentence_case_headings(text).text
    # First line ends with period → prose, NOT heading.
    assert "This Is A Title." in out


def test_transformations_count_recorded() -> None:
    res = sentence_case_headings("# One Two Three\n# Four Five Six")
    assert any("sentence_case:2" in t for t in res.transformations)
