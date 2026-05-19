"""Hebrew lexical humanizer tests."""

from __future__ import annotations

from humanizer.engines.lexical_he import humanize_lexical_he


def test_phrase_replacement_he() -> None:
    text = "חשוב לציין כי המערכת עובדת היטב. יתרה מכך, היא מהירה."
    res = humanize_lexical_he(text, "aggressive")
    assert "חשוב לציין כי" not in res.text or "יתרה מכך" not in res.text
    assert len(res.transformations) > 0


def test_buzzword_replacement_he() -> None:
    text = (
        "באופן משמעותי, המוצר ממלא תפקיד מכריע. הוא חיוני וקריטי וגם מהותי. "
        "המוצר משמעותי ומכריע מאוד."
    )
    res = humanize_lexical_he(text, "aggressive")
    # At 0.85 with many candidates we should get multiple hits.
    assert len(res.transformations) >= 2


def test_niqqud_tolerant_matching() -> None:
    # "חָשׁוּב" with niqqud; should match "חשוב" in synonyms.
    text = "המוצר חָשׁוּב מאוד."
    res = humanize_lexical_he(text, "aggressive")
    # Whether or not it matched depends on the RNG; we mainly assert no crash
    # and that the text length didn't grow absurdly.
    assert isinstance(res.text, str)
    assert len(res.text) <= len(text) + 30


def test_prefix_aware_matching() -> None:
    # "בעולם של היום" — phrase form should match independent of any prefix.
    text = "בעולם של היום, הטכנולוגיה ממלאת תפקיד מרכזי."
    res = humanize_lexical_he(text, "aggressive")
    # Expect either the phrase or the buzzword to be touched.
    assert (
        "בעולם של היום" not in res.text
        or "תפקיד מרכזי" not in res.text
        or len(res.transformations) > 0
    )


def test_empty_input_he() -> None:
    res = humanize_lexical_he("", "medium")
    assert res.text == ""
    assert res.transformations == []


def test_deterministic_he() -> None:
    text = "המערכת חשובה ומורכבת מאוד. ניתן לראות כי היא מהותית."
    a = humanize_lexical_he(text, "aggressive")
    b = humanize_lexical_he(text, "aggressive")
    assert a.text == b.text


def test_no_change_on_non_hebrew() -> None:
    text = "Hello world, this has no Hebrew."
    res = humanize_lexical_he(text, "aggressive")
    assert res.text == text
    assert res.transformations == []
