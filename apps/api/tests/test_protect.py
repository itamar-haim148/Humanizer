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


def test_sentence_initial_two_token_run_not_protected() -> None:
    """``Get Started today.`` — 2-token sentence-initial run is ambiguous
    (could just be a capitalised opener like "Click Here") so neither token
    is protected. The dictionaries themselves are responsible for not
    breaking these tokens."""
    text = "Get Started today by joining the program."
    ranges = protect.lexical_protected_ranges(text)
    started = text.index("Started")
    assert not protect.is_protected(started, ranges)


def test_sentence_initial_three_token_run_protects_tail() -> None:
    """``Yotpo Loyalty Setup is fast.`` — 3-token sentence-initial run keeps
    the first token free (it's the natural opener) but protects the rest."""
    text = "Yotpo Loyalty Setup is fast."
    ranges = protect.lexical_protected_ranges(text)
    yotpo = text.index("Yotpo")
    loyalty = text.index("Loyalty")
    setup = text.index("Setup")
    assert not protect.is_protected(yotpo, ranges)
    assert protect.is_protected(loyalty, ranges)
    assert protect.is_protected(setup, ranges)


def test_mid_sentence_two_token_run_fully_protected() -> None:
    """Mid-sentence ``Yotpo Loyalty`` is unambiguously a brand — protect
    both tokens."""
    text = "Switch to Yotpo Loyalty today."
    ranges = protect.lexical_protected_ranges(text)
    yotpo = text.index("Yotpo")
    loyalty = text.index("Loyalty")
    assert protect.is_protected(yotpo, ranges)
    assert protect.is_protected(loyalty, ranges)


# ---------------------------------------------------------------------------
# Markdown / social construct protection (StealthHumanizer-derived patterns)
# ---------------------------------------------------------------------------


def test_protects_markdown_link() -> None:
    text = "See [our docs](https://example.com/docs) for more info."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("[our docs]")
    end = text.index(")") + 1
    assert any(s <= start and e >= end for s, e in ranges)


def test_protects_markdown_image() -> None:
    text = "Logo: ![alt text](https://cdn.example.com/x.png) — nice."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("![alt text]")
    end = text.index(".png)") + len(".png)")
    assert any(s <= start and e >= end for s, e in ranges)


def test_protects_hashtag_and_mention() -> None:
    text = "Tagging @yotpo with #loyalty for context."
    ranges = protect.lexical_protected_ranges(text)
    at = text.index("@yotpo")
    hashtag = text.index("#loyalty")
    assert protect.is_protected(at, ranges)
    assert protect.is_protected(hashtag, ranges)


def test_blockquote_marker_protected_body_free() -> None:
    text = "> This block sentence has a verb and full punctuation here."
    [line] = protect.classify_lines(text)
    assert line.kind == "list_item"
    assert line.body_start > 0
    assert line.text[line.body_start:].startswith("This")
    ranges = protect.lexical_protected_ranges(text)
    # Marker protected.
    assert protect.is_protected(0, ranges)
    # Body free for transformation.
    body_idx = text.index("This")
    assert not protect.is_protected(body_idx, ranges)


def test_blockquote_short_body_promoted_to_heading() -> None:
    """A short blockquote without terminal punctuation behaves like a
    short list item — promoted to heading and fully protected."""
    text = "> TL DR Summary"
    [line] = protect.classify_lines(text)
    assert line.kind == "heading"


def test_markdown_link_with_parens_in_url() -> None:
    text = "See [Foo](https://en.wikipedia.org/wiki/Foo_(bar)) docs."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("[Foo]")
    end = text.rindex(")") + 1
    assert any(s <= start and e >= end for s, e in ranges)


def test_markdown_reference_link_protected() -> None:
    text = "Read [the manual][m1] before you start."
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("[the manual]")
    end = text.index("[m1]") + len("[m1]")
    assert any(s <= start and e >= end for s, e in ranges)


def test_markdown_reference_definition_protected() -> None:
    text = "Body line with verb.\n[m1]: https://example.com/docs Some Title"
    ranges = protect.lexical_protected_ranges(text)
    start = text.index("[m1]:")
    assert any(s <= start for s, _ in ranges)


def test_markdown_footnote_definition_not_protected() -> None:
    """`[^1]: ...` is a footnote definition (content), not a URL reference.
    Must remain transformable; the `(?!\\^)` exclusion in the regex prevents
    false-positive matching by the link-definition pattern."""
    text = "Body sentence here.\n[^1]: This footnote contains a complete prose sentence."
    ranges = protect.lexical_protected_ranges(text)
    footnote_idx = text.index("This footnote")
    assert not protect.is_protected(footnote_idx, ranges)
