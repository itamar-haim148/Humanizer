"""Pydantic schemas for Humanize + Detect API contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Language = Literal["en", "he"]
Strength = Literal["light", "medium", "aggressive"]
Verdict = Literal["human", "mixed", "ai"]

MAX_TEXT_LENGTH_HARD = 50_000  # Absolute ceiling; per-request is env-driven.


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class WatermarkFinding(BaseModel):
    kind: Literal[
        "zero_width",
        "nbsp",
        "control_char",
        "homoglyph",
        "bom",
        "non_standard_space",
    ]
    char: str
    codepoint: str  # e.g. "U+200B"
    index: int
    note: str | None = None


class CleaningReport(BaseModel):
    removed_count: int = 0
    normalized_count: int = 0
    findings: list[WatermarkFinding] = Field(default_factory=list)


class Metrics(BaseModel):
    """The 12 statistical detector metrics + the fused probability."""

    perplexity_proxy: float
    burstiness: float
    ai_phrase_density: float
    passive_voice_ratio: float
    transition_word_frequency: float
    vocab_diversity: float
    hedging_ratio: float
    sentence_start_diversity: float
    quantifier_overuse: float
    pronoun_pattern_score: float
    avg_sentence_length: float
    sentence_length_stdev: float

    ai_probability: float = Field(ge=0.0, le=1.0)
    verdict: Verdict


class Segment(BaseModel):
    start: int
    end: int
    text: str
    sub_score: float
    reason: str


class SynthIDResult(BaseModel):
    enabled: bool
    available: bool
    score: float | None = None
    detail: str | None = None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class HumanizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH_HARD)
    language: Language = "en"
    strength: Strength = "medium"
    clean_watermarks: bool = True

    @field_validator("text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must contain non-whitespace characters")
        return v  # preserve original spacing for engines


class DetectRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH_HARD)
    language: Language = "en"
    enable_synthid: bool = False

    @field_validator("text")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("text must contain non-whitespace characters")
        return v


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class HumanizeResponse(BaseModel):
    humanized_text: str
    metrics_before: Metrics
    metrics_after: Metrics
    transformations: list[str] = Field(default_factory=list)
    cleaning_report: CleaningReport
    language: Language
    strength: Strength
    latency_ms: float


class DetectResponse(BaseModel):
    ai_probability: float = Field(ge=0.0, le=1.0)
    verdict: Verdict
    metrics: Metrics
    watermark_findings: list[WatermarkFinding] = Field(default_factory=list)
    synthid: SynthIDResult | None = None
    highlighted_segments: list[Segment] = Field(default_factory=list)
    language: Language
    latency_ms: float


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None
