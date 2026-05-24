"""Tests for Layer 3 number humanization."""

from __future__ import annotations

from humanizer.engines.numbers import humanize_numbers


def test_bare_integer_comma_separated() -> None:
    assert humanize_numbers("We shipped 12500 units.").text == "We shipped 12,500 units."


def test_larger_integer() -> None:
    assert "1,234,567" in humanize_numbers("Revenue hit 1234567 last quarter.").text


def test_year_unchanged() -> None:
    assert "2026" in humanize_numbers("It launched in 2026.").text
    assert "2,026" not in humanize_numbers("It launched in 2026.").text


def test_year_1999_unchanged() -> None:
    assert "1999" in humanize_numbers("Born in 1999.").text


def test_already_formatted_skipped() -> None:
    text = "We hit 12,500 sales."
    assert humanize_numbers(text).text == text


def test_decimal_skipped() -> None:
    text = "The ratio is 12500.5 per unit."
    out = humanize_numbers(text).text
    assert "12500.5" in out
    assert "12,500.5" not in out


def test_post_hyphen_number_skipped() -> None:
    """A number preceded by a hyphen (range tail) stays bare."""
    text = "The range 1000-12500 was tested."
    out = humanize_numbers(text).text
    # "12500" is preceded by '-' → not humanized.
    assert "-12500" in out
    assert "-12,500" not in out


def test_url_protected() -> None:
    text = "Visit https://example.com/page/12500 for info."
    out = humanize_numbers(text).text
    assert "https://example.com/page/12500" in out


def test_code_span_protected() -> None:
    text = "Set `port = 12500` in config."
    out = humanize_numbers(text).text
    assert "`port = 12500`" in out


def test_three_digits_unchanged() -> None:
    """Only 4+ digit numbers get commas."""
    assert humanize_numbers("It is 999 units.").text == "It is 999 units."


def test_empty_input() -> None:
    assert humanize_numbers("").text == ""


def test_transformations_count() -> None:
    res = humanize_numbers("Sold 12500 and 8000 units.")
    assert any("comma_separated:2" in t for t in res.transformations)
