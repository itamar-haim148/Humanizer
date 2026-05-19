"""Tests for the content-segmentation / protection helpers."""

from __future__ import annotations

from humanizer.engines import protect


def test_classify_blank_line() -> None:
    lines = protect.classify_lines("")
    assert len(lines) == 1
    assert lines[0].kind == "blank"


def test_classify_short_heading_no_punctuation() -> None:
    [line] = protect.classify_lines("Flexible Earning Rules")
    assert line.kind == "heading"


def test_classify_numbered_heading() -> None:
    [line] = protect.classify_lines("1. Flexible Earning Rules")
    assert line.kind == "heading"


def test_classify_numbered_list_with_body() -> None:
    [line] = protect.classify_lines(
        "1. This is a full sentence with terminal punctuation explaining the item."
    )
    assert line.kind == "list_item"
    assert line.body_start > 0


def test_classify_label_line() -> None:
    [line] = protect.classify_lines(
        "Meta Title (48 characters): Create Flexible Earning Rules with Yotpo Loyalty"
    )
    assert line.kind == "label_line"
    assert line.text[line.body_start:].startswith("Create")


def test_classify_prose() -> None:
    [line] = protect.classify_lines(
        "Boost repeat purchases with Yotpo Loyalty by rewarding meaningful actions."
    )
    assert line.kind == "prose"


def test_classify_hebrew_heading() -> None:
    [line] = protect.classify_lines("כותרת ראשית")
    assert line.kind == "heading"


def test_classify_hash_heading() -> None:
    [line] = protect.classify_lines("## Section Title")
    assert line.kind == "heading"


# ---------------------------------------------------------------------------
# Protected ranges
# ---------------------------------------------------------------------------


def test_protects_proper_noun_run() -> None:
    text = "Switch to Yotpo Loyalty today."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("Yotpo Loyalty")
    end = start + len("Yotpo Loyalty")
    assert any(s <= start and e >= end for s, e in ranges)


def test_protects_parenthetical_meta() -> None:
    text = "Meta Title (48 characters): Anything goes here."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("(48 characters)")
    assert any(s <= start for s, _ in ranges)


def test_protects_url_and_email() -> None:
    text = "Visit https://example.com/path?x=1 or email foo@example.com today."
    ranges = protect.lexical_protected_ranges(text)
    assert any("example.com" in text[s:e] for s, e in ranges)


def test_protects_inline_code() -> None:
    text = "Run `npm install --save` to set up."
    ranges = protect.lexical_protected_ranges(text)
    needle = text.index("`npm install --save`")
    assert any(s <= needle for s, _ in ranges)


def test_protects_heading_lines_fully() -> None:
    text = "1. Flexible Earning Rules\nThis is a body sentence with a verb here."
    ranges = protect.lexical_protected_ranges(text)
    heading_end = text.index("\n")
    assert any(s == 0 and e >= heading_end for s, e in ranges)


def test_sentence_initial_proper_noun_drops_first_token() -> None:
    text = "Yotpo Loyalty is great."
    ranges = protect.lexical_protected_ranges(text)
    # Drop "Yotpo" from the protected run (sentence-initial), keep "Loyalty".
    yotpo_start = text.index("Yotpo")
    loyalty_start = text.index("Loyalty")
    # Yotpo should NOT be inside a protected range (sentence-initial fall-through).
    # But for a fresh sentence start the heuristic still protects from the
    # second token. We assert the second token is protected.
    assert protect.is_protected(loyalty_start, ranges)
    # And the bare word "Yotpo" by itself shouldn't be inside a protected run.
    assert not protect.is_protected(yotpo_start, ranges)
