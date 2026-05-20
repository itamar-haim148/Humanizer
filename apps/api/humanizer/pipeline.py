"""Pipeline orchestrator — composes engines into Humanize + Detect flows.

Humanize:
    cleaner → lexical (per language) → structural → cleaner (final pass)
    → detect before & after for the metrics_before / metrics_after pair.

Detect:
    statistical (12 metrics) → fused ai_probability → verdict
    + watermark report
    + optional SynthID
    + highlighted_segments (top-N highest-scoring sentences).
"""

from __future__ import annotations

import re
import time

from humanizer.engines import (
    cleaner,
    detector_statistical,
    detector_synthid,
    detector_watermark,
    lexical_en,
    lexical_he,
    llm_polish,
    post_llm_polish,
    structural,
)
from humanizer.models import (
    DetectRequest,
    DetectResponse,
    HumanizeLLMResponse,
    HumanizeRequest,
    HumanizeResponse,
    Metrics,
    Segment,
    Verdict,
)

# ---------------------------------------------------------------------------
# Fusion weights — must sum to 1.0
# ---------------------------------------------------------------------------

_SUB_WEIGHTS: dict[str, float] = {
    "perplexity_sub": 0.14,
    "burstiness_sub": 0.14,
    "ai_phrase_density_sub": 0.16,
    "passive_voice_sub": 0.06,
    "transition_sub": 0.08,
    "vocab_diversity_sub": 0.10,
    "hedging_sub": 0.04,
    "sentence_start_diversity_sub": 0.08,
    "quantifier_sub": 0.06,
    "pronoun_sub": 0.14,
}
assert abs(sum(_SUB_WEIGHTS.values()) - 1.0) < 1e-6

_VERDICT_LOW = 0.35
_VERDICT_HIGH = 0.65


def _fuse(stats: dict[str, float]) -> float:
    total = 0.0
    for k, w in _SUB_WEIGHTS.items():
        total += w * stats.get(k, 0.0)
    return max(0.0, min(1.0, total))


def _to_verdict(p: float) -> Verdict:
    if p < _VERDICT_LOW:
        return "human"
    if p < _VERDICT_HIGH:
        return "mixed"
    return "ai"


def _build_metrics(stats: dict[str, float], probability: float) -> Metrics:
    return Metrics(
        perplexity_proxy=stats.get("perplexity_proxy", 0.0),
        burstiness=stats.get("burstiness", 0.0),
        ai_phrase_density=stats.get("ai_phrase_density", 0.0),
        passive_voice_ratio=stats.get("passive_voice_ratio", 0.0),
        transition_word_frequency=stats.get("transition_word_frequency", 0.0),
        vocab_diversity=stats.get("vocab_diversity", 0.0),
        hedging_ratio=stats.get("hedging_ratio", 0.0),
        sentence_start_diversity=stats.get("sentence_start_diversity", 0.0),
        quantifier_overuse=stats.get("quantifier_overuse", 0.0),
        pronoun_pattern_score=stats.get("pronoun_pattern_score", 0.0),
        avg_sentence_length=stats.get("avg_sentence_length", 0.0),
        sentence_length_stdev=stats.get("sentence_length_stdev", 0.0),
        ai_probability=probability,
        verdict=_to_verdict(probability),
    )


# ---------------------------------------------------------------------------
# Highlighted segments — pick top-N sentences with the most AI-like signals
# ---------------------------------------------------------------------------

_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def _highlighted_segments(
    text: str, language: str, top_n: int = 5
) -> list[Segment]:
    segments: list[Segment] = []
    sentences: list[tuple[int, int, str]] = []
    cursor = 0
    for piece in _SENT_BOUNDARY.split(text):
        if not piece:
            continue
        start = text.find(piece, cursor)
        if start < 0:
            continue
        end = start + len(piece)
        sentences.append((start, end, piece))
        cursor = end

    for start, end, sentence in sentences:
        if len(sentence.split()) < 3:
            continue
        stats = detector_statistical.compute_all(sentence, language)  # type: ignore[arg-type]
        sub = _fuse(stats)
        reason = _pick_reason(stats)
        segments.append(
            Segment(
                start=start,
                end=end,
                text=sentence,
                sub_score=sub,
                reason=reason,
            )
        )

    segments.sort(key=lambda s: s.sub_score, reverse=True)
    return segments[:top_n]


def _pick_reason(stats: dict[str, float]) -> str:
    candidates = [
        ("ai_phrase_density_sub", "AI phrase density"),
        ("burstiness_sub", "Low burstiness"),
        ("perplexity_sub", "Predictable vocabulary"),
        ("passive_voice_sub", "Passive voice"),
        ("transition_sub", "Transition overuse"),
        ("pronoun_sub", "Pronoun pattern"),
    ]
    top = max(candidates, key=lambda kv: stats.get(kv[0], 0.0))
    return top[1]


# ---------------------------------------------------------------------------
# Humanize
# ---------------------------------------------------------------------------


def run_humanize(req: HumanizeRequest) -> HumanizeResponse:
    started = time.perf_counter()

    metrics_before_stats = detector_statistical.compute_all(req.text, req.language)
    metrics_before = _build_metrics(
        metrics_before_stats, _fuse(metrics_before_stats)
    )

    working = req.text
    transformations: list[str] = []
    cleaning = cleaner.clean(working) if req.clean_watermarks else cleaner.CleanResult(cleaned_text=working)
    working = cleaning.cleaned_text

    if req.language == "en":
        lex_en = lexical_en.humanize_lexical(working, req.strength)
        working = lex_en.text
        transformations.extend(lex_en.transformations)
    else:
        lex_he = lexical_he.humanize_lexical_he(working, req.strength)
        working = lex_he.text
        transformations.extend(lex_he.transformations)

    working = structural.humanize_structural(working, req.language, req.strength)

    final_clean = cleaner.clean(working)
    working = final_clean.cleaned_text

    metrics_after_stats = detector_statistical.compute_all(working, req.language)
    metrics_after = _build_metrics(
        metrics_after_stats, _fuse(metrics_after_stats)
    )

    latency = round((time.perf_counter() - started) * 1000, 2)
    return HumanizeResponse(
        humanized_text=working,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        transformations=transformations[:50],
        cleaning_report=cleaning.to_report(),
        language=req.language,
        strength=req.strength,
        latency_ms=latency,
    )


# ---------------------------------------------------------------------------
# Humanize + LLM polish (gated, requires Gemini API key + auth)
# ---------------------------------------------------------------------------


async def run_humanize_llm(req: HumanizeRequest, api_key: str) -> HumanizeLLMResponse:
    """LLM first, then scrub its output with the statistical pipeline.

    Order: cleaner(input) -> LLM polish -> cleaner -> post_llm_polish (EN)
           -> lexical -> structural -> cleaner.

    Why LLM-first:
    - Gemini rewrites for natural human voice but routinely re-introduces
      AI tells ("delve", "leverage", "moreover") and can echo invisible
      watermark characters back into the text. Running the deterministic
      Python pipeline *after* the LLM removes those final-mile traces.
    - The initial cleaner still strips watermarks from the user's input so
      Gemini never sees them and never echoes them back.

    Raises llm_polish.LLMPolishError on Gemini failure; caller maps to HTTP 502.
    """
    started = time.perf_counter()

    metrics_before_stats = detector_statistical.compute_all(req.text, req.language)
    metrics_before = _build_metrics(
        metrics_before_stats, _fuse(metrics_before_stats)
    )

    working = req.text
    transformations: list[str] = []
    cleaning = (
        cleaner.clean(working)
        if req.clean_watermarks
        else cleaner.CleanResult(cleaned_text=working)
    )
    working = cleaning.cleaned_text

    # 1. LLM polish on the cleaned input.
    polish_result = await llm_polish.polish(
        text=working,
        language=req.language,
        strength=req.strength,
        api_key=api_key,
    )
    working = polish_result.text
    transformations.append(f"llm_polish:{polish_result.model}")

    # 2. Scrub the LLM output: watermarks first (so the lexical/structural
    #    engines see clean text), then LLM-specific structural tells
    #    (semicolon-pivots, intensifier adjectives), then AI vocabulary,
    #    then sentence-shape rewrites.
    post_clean = cleaner.clean(working)
    working = post_clean.cleaned_text

    # 2b. Post-LLM pattern fixes — only meaningful in LLM mode because
    #     these target Gemini/GPT rewrite habits that the regular pipeline
    #     never has to deal with.
    if req.language == "en":
        post_polish = post_llm_polish.polish(working, req.strength)
        working = post_polish.text
        transformations.extend(post_polish.transformations)

    if req.language == "en":
        lex_en = lexical_en.humanize_lexical(working, req.strength)
        working = lex_en.text
        transformations.extend(lex_en.transformations)
    else:
        lex_he = lexical_he.humanize_lexical_he(working, req.strength)
        working = lex_he.text
        transformations.extend(lex_he.transformations)

    working = structural.humanize_structural(working, req.language, req.strength)

    # 3. Defence-in-depth final clean.
    final_clean = cleaner.clean(working)
    working = final_clean.cleaned_text

    metrics_after_stats = detector_statistical.compute_all(working, req.language)
    metrics_after = _build_metrics(metrics_after_stats, _fuse(metrics_after_stats))

    latency = round((time.perf_counter() - started) * 1000, 2)
    return HumanizeLLMResponse(
        humanized_text=working,
        metrics_before=metrics_before,
        metrics_after=metrics_after,
        transformations=transformations[:50],
        cleaning_report=cleaning.to_report(),
        language=req.language,
        strength=req.strength,
        latency_ms=latency,
        llm_model=polish_result.model,
        llm_prompt_tokens=polish_result.prompt_tokens,
        llm_output_tokens=polish_result.output_tokens,
    )


# ---------------------------------------------------------------------------
# Detect
# ---------------------------------------------------------------------------


def run_detect(req: DetectRequest) -> DetectResponse:
    started = time.perf_counter()
    stats = detector_statistical.compute_all(req.text, req.language)
    probability = _fuse(stats)
    metrics = _build_metrics(stats, probability)
    wm_report = detector_watermark.detect_watermarks(req.text)
    synthid = detector_synthid.detect_synthid(req.text) if req.enable_synthid else None
    segments = _highlighted_segments(req.text, req.language)
    latency = round((time.perf_counter() - started) * 1000, 2)

    return DetectResponse(
        ai_probability=probability,
        verdict=_to_verdict(probability),
        metrics=metrics,
        watermark_findings=wm_report.findings,
        synthid=synthid,
        highlighted_segments=segments,
        language=req.language,
        latency_ms=latency,
    )
