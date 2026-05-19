"""Watermark detector tests."""

from __future__ import annotations

from humanizer.engines.detector_watermark import detect_watermarks


def test_zero_width_detected() -> None:
    report = detect_watermarks("hello\u200B world\u200C")
    assert report.zero_width_count == 2
    assert report.total == 2


def test_nbsp_detected() -> None:
    report = detect_watermarks("a\u00A0b")
    assert report.nbsp_count == 1


def test_homoglyph_detected() -> None:
    text = "Word \u2160 next"
    report = detect_watermarks(text)
    assert report.homoglyph_count >= 1


def test_clean_text_no_findings() -> None:
    report = detect_watermarks("Hello world. How are you?")
    assert report.total == 0
    assert report.findings == []


def test_to_dict_serializable() -> None:
    report = detect_watermarks("a\u200Bb\u00A0c")
    d = report.to_dict()
    assert d["zero_width_count"] == 1
    assert d["nbsp_count"] == 1
    assert isinstance(d["findings"], list)
    assert len(d["findings"]) == 2
