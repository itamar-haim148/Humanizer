"""Schema validation tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from humanizer.models import (
    DetectRequest,
    DetectResponse,
    HumanizeRequest,
    HumanizeResponse,
    Metrics,
    CleaningReport,
)


def _metrics() -> Metrics:
    return Metrics(
        perplexity_proxy=0.5,
        burstiness=0.4,
        ai_phrase_density=0.1,
        passive_voice_ratio=0.2,
        transition_word_frequency=0.3,
        vocab_diversity=0.6,
        hedging_ratio=0.05,
        sentence_start_diversity=0.7,
        quantifier_overuse=0.1,
        pronoun_pattern_score=0.4,
        avg_sentence_length=18.5,
        sentence_length_stdev=6.1,
        ai_probability=0.42,
        verdict="mixed",
    )


def test_humanize_request_valid() -> None:
    req = HumanizeRequest(text="Hello world.", language="en", strength="medium")
    assert req.text == "Hello world."
    assert req.clean_watermarks is True


def test_humanize_request_rejects_blank() -> None:
    with pytest.raises(ValidationError):
        HumanizeRequest(text="   \n\t  ", language="en", strength="medium")


def test_humanize_request_rejects_oversize() -> None:
    with pytest.raises(ValidationError):
        HumanizeRequest(text="x" * 60_000, language="en", strength="light")


def test_detect_request_valid_hebrew() -> None:
    req = DetectRequest(text="שלום עולם.", language="he")
    assert req.language == "he"
    assert req.enable_synthid is False


def test_humanize_response_roundtrip() -> None:
    m = _metrics()
    resp = HumanizeResponse(
        humanized_text="Hi there.",
        metrics_before=m,
        metrics_after=m,
        transformations=["removed 'delve'"],
        cleaning_report=CleaningReport(),
        language="en",
        strength="medium",
        latency_ms=42.0,
    )
    dumped = resp.model_dump()
    assert dumped["humanized_text"] == "Hi there."
    assert dumped["metrics_before"]["verdict"] == "mixed"


def test_detect_response_probability_bounds() -> None:
    m = _metrics()
    with pytest.raises(ValidationError):
        DetectResponse(
            ai_probability=1.5,  # out of bounds
            verdict="ai",
            metrics=m,
            language="en",
            latency_ms=10.0,
        )


def test_metrics_verdict_literal() -> None:
    with pytest.raises(ValidationError):
        Metrics(
            perplexity_proxy=0.5,
            burstiness=0.4,
            ai_phrase_density=0.1,
            passive_voice_ratio=0.2,
            transition_word_frequency=0.3,
            vocab_diversity=0.6,
            hedging_ratio=0.05,
            sentence_start_diversity=0.7,
            quantifier_overuse=0.1,
            pronoun_pattern_score=0.4,
            avg_sentence_length=18.5,
            sentence_length_stdev=6.1,
            ai_probability=0.42,
            verdict="unknown",  # type: ignore[arg-type]
        )
