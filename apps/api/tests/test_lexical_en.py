"""English lexical humanizer tests."""

from __future__ import annotations

from humanizer.engines.lexical_en import humanize_lexical


def test_removes_delve_aggressive() -> None:
    # Many occurrences so 0.85 ratio reliably hits some.
    text = (
        "We delve into things. They delve. He delves too. "
        "She is delving. We delved before."
    )
    res = humanize_lexical(text, "aggressive")
    delve_hits = sum(t.startswith("word: '") and "delv" in t.lower() for t in res.transformations)
    assert delve_hits >= 1
    assert len(res.transformations) > 0


def test_removes_moreover_medium() -> None:
    # Use many AI-typical words so 0.50 reliably catches some.
    text = (
        "Moreover, this is good. Furthermore, it works. "
        "Additionally, the results are robust. "
        "Subsequently, the system is seamless."
    )
    res = humanize_lexical(text, "medium")
    assert len(res.transformations) >= 1


def test_phrase_replacement() -> None:
    text = "It is important to note that this matters."
    res = humanize_lexical(text, "aggressive")
    assert "it is important to note that" not in res.text.lower()


def test_preserves_unmatched_text() -> None:
    text = "Cats and dogs are great pets."
    res = humanize_lexical(text, "light")
    # Most words won't have synonyms or AI hits; text should remain mostly intact.
    assert "pets" in res.text or "Pets" in res.text


def test_case_preservation() -> None:
    text = "Delve in. DELVE!"
    res = humanize_lexical(text, "aggressive")
    # First match capitalized, second uppercase — replacement should respect that.
    assert any(c.isupper() for c in res.text)


def test_empty_input() -> None:
    res = humanize_lexical("", "medium")
    assert res.text == ""
    assert res.transformations == []


def test_deterministic_seed() -> None:
    text = "We delve into the realm of complex systems with myriad challenges."
    a = humanize_lexical(text, "aggressive")
    b = humanize_lexical(text, "aggressive")
    assert a.text == b.text


def test_strength_levels_differ() -> None:
    text = "Furthermore, we must delve into this and leverage the system."
    light = humanize_lexical(text, "light")
    aggressive = humanize_lexical(text, "aggressive")
    # Aggressive should have at least as many transformations as light.
    assert len(aggressive.transformations) >= len(light.transformations)


def test_transformations_logged() -> None:
    text = "We delve into the realm."
    res = humanize_lexical(text, "aggressive")
    assert all(":" in t and "'" in t for t in res.transformations)
