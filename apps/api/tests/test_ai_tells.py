"""Tests for Layer 2 AI-tell scrubber."""

from __future__ import annotations

from humanizer.engines.ai_tells import scrub_ai_tells


def test_signpost_transitions_stripped() -> None:
    text = "Furthermore, the data is clear. Moreover, we shipped on time."
    out = scrub_ai_tells(text, "medium").text
    assert "Furthermore," not in out
    assert "Moreover," not in out


def test_additionally_softened() -> None:
    text = "Additionally, we added support."
    out = scrub_ai_tells(text, "medium").text
    assert "Additionally," not in out
    assert "Also," in out


def test_serves_as_collapsed() -> None:
    text = "The team serves as a vehicle for change."
    out = scrub_ai_tells(text, "medium").text
    assert "serves as a" not in out
    assert "is a vehicle" in out


def test_in_order_to_shortened() -> None:
    out = scrub_ai_tells("We did this in order to ship faster.", "medium").text
    assert "in order to" not in out
    assert "to ship" in out


def test_chatbot_artifact_removed() -> None:
    out = scrub_ai_tells("As an AI language model, I think this works.", "medium").text
    assert "As an AI" not in out


def test_landscape_phrase_removed() -> None:
    out = scrub_ai_tells(
        "In today's digital landscape, brands must adapt.", "medium"
    ).text
    assert "digital landscape" not in out
    assert "in today" not in out.lower()


def test_let_us_dive_in_stripped() -> None:
    out = scrub_ai_tells("Let's dive in. Here's the plan.", "medium").text
    assert "dive in" not in out


def test_delve_into_replaced() -> None:
    out = scrub_ai_tells("Let us delve into the numbers.", "medium").text
    assert "delve into" not in out
    assert "examine" in out


def test_protected_url_untouched() -> None:
    text = "Visit https://example.com/in-order-to/path for details."
    out = scrub_ai_tells(text, "medium").text
    assert "https://example.com/in-order-to/path" in out


def test_light_strength_still_scrubs() -> None:
    """Layer 2 is always-on regardless of strength."""
    text = "Furthermore, things matter."
    out = scrub_ai_tells(text, "light").text
    assert "Furthermore," not in out


def test_empty_input() -> None:
    assert scrub_ai_tells("", "medium").text == ""


def test_transformations_logged() -> None:
    res = scrub_ai_tells("Furthermore, we delve into data.", "medium")
    assert any("furthermore_sentence" in t for t in res.transformations)
    assert any("delve_into" in t for t in res.transformations)
