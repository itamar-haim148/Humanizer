"""Verifies fixtures separate AI from human samples on the fused score."""

from __future__ import annotations

import json
from pathlib import Path

from humanizer.models import DetectRequest
from humanizer.pipeline import run_detect

_FIX = Path(__file__).parent / "fixtures"


def _load(name: str) -> list[str]:
    with (_FIX / name).open(encoding="utf-8") as f:
        return list(json.load(f))


def _mean_score(samples: list[str], lang: str) -> float:
    scores = [
        run_detect(DetectRequest(text=s, language=lang)).ai_probability  # type: ignore[arg-type]
        for s in samples
    ]
    return sum(scores) / len(scores)


def test_en_ai_scores_higher_than_human() -> None:
    ai = _mean_score(_load("ai_en.json"), "en")
    human = _mean_score(_load("human_en.json"), "en")
    assert ai > human


def test_he_ai_scores_higher_than_human() -> None:
    ai = _mean_score(_load("ai_he.json"), "he")
    human = _mean_score(_load("human_he.json"), "he")
    assert ai > human
