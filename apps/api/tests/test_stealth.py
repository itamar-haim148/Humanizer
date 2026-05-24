"""Tests for Layer 6 stealth pass (perplexity + burstiness)."""

from __future__ import annotations

from humanizer.engines.stealth import stealth_pass


def test_perplexity_swaps_some_tokens() -> None:
    text = (
        "The data shows results. The analysis demonstrates progress. "
        "We need to optimize performance. The system is robust and effective."
    )
    out = stealth_pass(text, "medium", seed=42).text
    # Some swap should have happened — at least one perplexity-vocab token is gone.
    swapped = any(tok not in out for tok in ("shows", "demonstrates", "optimize", "robust"))
    assert swapped


def test_deterministic_seed() -> None:
    text = "The analysis shows results. We need to optimize the design."
    a = stealth_pass(text, "medium", seed=7).text
    b = stealth_pass(text, "medium", seed=7).text
    assert a == b


def test_different_seeds_can_differ() -> None:
    text = (
        "Shows results. Demonstrates progress. Optimize systems. Robust design. "
        "Important features. Various inputs. Comprehensive coverage. Effective work."
    )
    a = stealth_pass(text, "medium", seed=1).text
    b = stealth_pass(text, "medium", seed=99).text
    # Not guaranteed for every seed-pair but vanishingly unlikely with this corpus.
    assert a != b


def test_url_protected() -> None:
    text = "Read more at https://example.com/shows/optimize/robust here."
    out = stealth_pass(text, "medium", seed=42).text
    assert "https://example.com/shows/optimize/robust" in out


def test_code_protected() -> None:
    text = "Use `shows()` and `optimize()` functions."
    out = stealth_pass(text, "medium", seed=42).text
    assert "`shows()`" in out
    assert "`optimize()`" in out


def test_empty_input() -> None:
    assert stealth_pass("", "medium").text == ""


def test_aggressive_runs_two_passes() -> None:
    """Aggressive should produce at least as many swaps as medium."""
    text = (
        "The data shows X. Shows Y. Shows Z. "
        "The system demonstrates A. Demonstrates B. Demonstrates C."
    )
    med = stealth_pass(text, "medium", seed=42)
    agg = stealth_pass(text, "aggressive", seed=42)
    med_swaps = sum(int(t.split(":")[-1]) for t in med.transformations if "perplexity" in t)
    agg_swaps = sum(int(t.split(":")[-1]) for t in agg.transformations if "perplexity" in t)
    assert agg_swaps >= med_swaps


def test_burstiness_fragment_skipped_in_lists() -> None:
    text = (
        "- This bullet item is long enough to clear the twenty word threshold "
        "easily without effort because regression test inputs sometimes need to be long.\n"
        "- Another item that is also long enough to clear the same twenty word "
        "threshold so that burstiness injection would normally fire on it."
    )
    out = stealth_pass(text, "medium", seed=42).text
    # No emphasis fragments should be injected after list items.
    for frag in ("That matters here.", "And it shows in the data.",
                 "The shift is not subtle.", "The math is plain."):
        assert frag not in out


def test_case_preservation_on_swap() -> None:
    text = "Shows that everything is working. Demonstrates the value clearly."
    out = stealth_pass(text, "medium", seed=42).text
    # If the leading word swapped, the replacement should start uppercase.
    first_word = out.split()[0]
    assert first_word[0].isupper()
