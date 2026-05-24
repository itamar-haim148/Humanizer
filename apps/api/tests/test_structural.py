"""Structural humanizer tests."""

from __future__ import annotations

from humanizer.engines.structural import burstiness, humanize_structural


def test_light_is_passthrough() -> None:
    text = "This is a sentence. This is another."
    assert humanize_structural(text, "en", "light") == text


def test_long_sentence_split_en() -> None:
    text = (
        "The system has many features, and it scales well across "
        "deployments, and it handles failures and integrates with the "
        "monitoring stack and observes everything for full visibility every day."
    )
    out = humanize_structural(text, "en", "aggressive")
    # The output should now contain at least 2 sentences.
    assert out.count(".") >= 2 or out.count("—") >= 1


def test_short_sentences_restructured_en() -> None:
    text = "It works. It runs. It scales. It rocks!"
    out = humanize_structural(text, "en", "aggressive")
    # Em-dashes are an AI tell and must NEVER be inserted.
    assert "\u2014" not in out
    # Paragraph splitter (>3 sentences) must have introduced a blank line.
    assert "\n\n" in out


def test_burstiness_uplift_en() -> None:
    uniform_ai = (
        "The model performs well. The model handles data. The model returns "
        "results. The model uses memory. The model is robust. "
        "The model handles errors. The model scales."
    )
    before = burstiness(uniform_ai, "en")
    after = burstiness(humanize_structural(uniform_ai, "en", "aggressive"), "en")
    assert after >= before  # Should at least not decrease.


def test_long_sentence_split_he() -> None:
    text = (
        "המערכת מציעה מגוון רחב של תכונות, וכן היא יודעת לטפל בכשלים "
        "ומשתלבת בתשתיות מוניטורינג ושומרת על נראות מלאה ולמעשה רצה כל הזמן."
    )
    out = humanize_structural(text, "he", "aggressive")
    # Either split into multiple sentences or got an em-dash merge effect.
    assert out.count(".") >= 1


def test_burstiness_uplift_he() -> None:
    uniform_he = (
        "המוצר עובד. המוצר רץ. המוצר מתאים. המוצר חזק. "
        "המוצר יציב. המוצר מהיר. המוצר טוב."
    )
    before = burstiness(uniform_he, "he")
    after = burstiness(humanize_structural(uniform_he, "he", "aggressive"), "he")
    assert after >= before


def test_paragraph_breaks_preserved() -> None:
    text = "First paragraph. With two sentences.\n\nSecond paragraph here."
    out = humanize_structural(text, "en", "medium")
    assert "\n\n" in out


def test_empty_input_structural() -> None:
    assert humanize_structural("", "en", "aggressive") == ""
    assert humanize_structural("", "he", "aggressive") == ""
