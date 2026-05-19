"""Cleaner engine tests."""

from __future__ import annotations

from humanizer.engines.cleaner import BOM, clean, detect_only


def test_strips_zero_width() -> None:
    text = "Hello\u200B world\u200C foo\u200D bar\u2060."
    res = clean(text)
    assert res.cleaned_text == "Hello world foo bar."
    assert res.removed_count == 4
    assert all(f.kind == "zero_width" for f in res.findings)


def test_normalizes_nbsp_to_space() -> None:
    text = "a\u00A0b\u202Fc"
    res = clean(text)
    assert res.cleaned_text == "a b c"
    assert res.normalized_count == 2
    kinds = {f.kind for f in res.findings}
    assert "nbsp" in kinds
    assert "non_standard_space" in kinds


def test_preserves_leading_bom() -> None:
    text = f"{BOM}hello"
    res = clean(text)
    assert res.cleaned_text == f"{BOM}hello"
    assert res.removed_count == 0


def test_strips_mid_text_bom() -> None:
    text = f"hello{BOM}world"
    res = clean(text)
    assert res.cleaned_text == "helloworld"
    assert res.removed_count == 1
    assert res.findings[0].kind == "bom"


def test_strips_control_chars_but_keeps_newline_tab() -> None:
    text = "a\nb\tc\x07d"
    res = clean(text)
    assert res.cleaned_text == "a\nb\tc d" or res.cleaned_text == "a\nb\tcd"
    # \x07 is BEL (Cc) — must be removed; \n and \t preserved
    assert "\x07" not in res.cleaned_text
    assert "\n" in res.cleaned_text
    assert "\t" in res.cleaned_text


def test_homoglyph_detected() -> None:
    # Greek Alpha (U+0391) vs Latin A (U+0041) — NFKC won't change them, so use
    # a compatibility character that NFKC normalizes. Roman numeral Ⅰ (U+2160)
    # normalizes to ASCII 'I'.
    text = "Word \u2160 next"
    res = clean(text)
    assert "I" in res.cleaned_text
    assert any(f.kind == "homoglyph" for f in res.findings)


def test_detect_only_does_not_mutate() -> None:
    text = "a\u200Bb"
    findings = detect_only(text)
    assert len(findings) == 1
    assert findings[0].kind == "zero_width"


def test_empty_string() -> None:
    res = clean("")
    assert res.cleaned_text == ""
    assert res.findings == []


def test_hebrew_preserved() -> None:
    text = "שלום\u200B עולם"
    res = clean(text)
    assert res.cleaned_text == "שלום עולם"
    assert res.removed_count == 1


def test_to_report_serializable() -> None:
    text = "a\u200Bb"
    rep = clean(text).to_report()
    dumped = rep.model_dump()
    assert dumped["removed_count"] == 1
    assert dumped["findings"][0]["kind"] == "zero_width"
