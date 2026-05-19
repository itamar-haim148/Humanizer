"""Statistical detector tests."""

from __future__ import annotations

import importlib

from humanizer.engines import detector_statistical as ds


def setup_module(_: object) -> None:
    # Reload to pick up freq files if they were just written by the test runner.
    importlib.reload(ds)


# ---------------------------------------------------------------------------
# Part 1 — perplexity proxy + burstiness
# ---------------------------------------------------------------------------


def test_part1_uniform_ai_high_score_en() -> None:
    text = (
        "The model performs well. The model handles data. The model returns results. "
        "The model uses memory efficiently. The model is robust."
    )
    res = ds.compute_part1(text, "en")
    assert res["burstiness"] < 0.4
    assert res["burstiness_sub"] > 0.5
    assert res["avg_sentence_length"] > 3


def test_part1_bursty_human_low_score_en() -> None:
    text = (
        "I dunno. Maybe? Well, listen — when I went there, I saw a tall man with a "
        "small dog, who looked at me, and I waved. He left."
    )
    res = ds.compute_part1(text, "en")
    assert res["burstiness"] > 0.4


def test_part1_hebrew() -> None:
    text = "המוצר עובד. המוצר רץ. המוצר טוב. המוצר מהיר."
    res = ds.compute_part1(text, "he")
    assert res["burstiness"] < 0.4
    assert res["burstiness_sub"] > 0.4


# ---------------------------------------------------------------------------
# Part 2 — AI phrase density + passive + transitions
# ---------------------------------------------------------------------------


def test_part2_high_density_en() -> None:
    text = (
        "Furthermore, the system delves into the realm of robust automation. "
        "Moreover, it leverages a plethora of features. "
        "Additionally, navigating these intricate landscapes is crucial."
    )
    res = ds.compute_part2(text, "en")
    assert res["ai_phrase_density"] > 0.04
    assert res["transition_word_frequency"] > 0.03


def test_part2_low_density_human_en() -> None:
    text = "Yesterday I went for a walk. The dog chased a squirrel. We laughed."
    res = ds.compute_part2(text, "en")
    assert res["ai_phrase_density"] < 0.02
    assert res["transition_word_frequency"] < 0.03


def test_part2_hebrew_density() -> None:
    text = (
        "יתרה מכך, המערכת משמעותית ומכריעה. בנוסף, היא חיונית וקריטית. "
        "אולם, ניתן לראות כי תפקידה מרכזי."
    )
    res = ds.compute_part2(text, "he")
    assert res["ai_phrase_density"] > 0.02


def test_part2_passive_voice() -> None:
    text = "The cake was eaten. The door was opened. The book was written."
    res = ds.compute_part2(text, "en")
    assert res["passive_voice_ratio"] > 0.5


# ---------------------------------------------------------------------------
# Part 3 — vocab/hedging/diversity/quantifiers/pronouns
# ---------------------------------------------------------------------------


def test_part3_low_vocab_diversity_en() -> None:
    text = "The model the model the model. The model the model the model."
    res = ds.compute_part3(text, "en")
    assert res["vocab_diversity"] < 0.4
    assert res["vocab_diversity_sub"] > 0.4


def test_part3_high_vocab_diversity_en() -> None:
    text = (
        "Yesterday I wandered through colorful alleys, photographing strangers, "
        "drinking espresso, laughing with locals, sketching ancient bridges."
    )
    res = ds.compute_part3(text, "en")
    assert res["vocab_diversity"] > 0.55


def test_part3_hedging_en() -> None:
    text = (
        "Perhaps the model might possibly work. It could maybe arguably "
        "potentially handle most cases. Likely it presumably suffices."
    )
    res = ds.compute_part3(text, "en")
    assert res["hedging_ratio"] > 0.05


def test_part3_pronoun_pattern_low_for_ai() -> None:
    text = (
        "The system processes data. The model handles queries. The framework "
        "manages state. The platform delivers results."
    )
    res = ds.compute_part3(text, "en")
    assert res["pronoun_pattern_score"] < 0.02


def test_part3_pronoun_pattern_high_for_human() -> None:
    text = "I went home. We talked. You said it. They left us alone."
    res = ds.compute_part3(text, "en")
    assert res["pronoun_pattern_score"] > 0.15


def test_compute_all_includes_all_keys() -> None:
    text = "Sample text. Some sentences."
    res = ds.compute_all(text, "en")
    expected = {
        "perplexity_proxy", "perplexity_sub",
        "burstiness", "burstiness_sub",
        "avg_sentence_length", "sentence_length_stdev",
        "ai_phrase_density", "ai_phrase_density_sub",
        "passive_voice_ratio", "passive_voice_sub",
        "transition_word_frequency", "transition_sub",
        "vocab_diversity", "vocab_diversity_sub",
        "hedging_ratio", "hedging_sub",
        "sentence_start_diversity", "sentence_start_diversity_sub",
        "quantifier_overuse", "quantifier_sub",
        "pronoun_pattern_score", "pronoun_sub",
    }
    assert expected.issubset(res.keys())


def test_empty_text() -> None:
    res = ds.compute_all("", "en")
    assert res["burstiness"] == 0.0
    assert res["ai_phrase_density"] == 0.0
