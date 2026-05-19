# Engines

This document records the provenance, behavior, and operational knobs of each
engine in the Humanize platform.

## Watermark cleaner — `engines/cleaner.py`
- Sources: Markless-GPT (MIT), Text-Stealth-Watermark-Cleaner-Detector
- Strips invisible Unicode (zero-width, NBSP, BOM, control chars), applies NFKC
- Returns `CleanResult{cleaned_text, findings}`

## English lexical humanizer — `engines/lexical_en.py`
- Source: OrbitWebTools/Humanize-AI (port JS → Python)
- AI phrase dict + 400+ general synonyms, strength-driven deterministic RNG
- Light/Medium/Aggressive = 0.20 / 0.50 / 0.85 swap ratio

## Hebrew lexical humanizer — `engines/lexical_he.py`
- Niqqud-tolerant matching (U+0591–U+05C7 stripped for compare, dropped on swap)
- Prefix-aware: ה / ו / ב / ל / מ / כ / ש + combos

## Structural humanizer — `engines/structural.py`
- Splits long sentences at conjunctions; merges short adjacent sentences
- Adds punchy openers per paragraph (medium+)

## Statistical detector — `engines/detector_statistical.py`
- 12 metrics + normalized 0–1 sub-scores; pure-Python, no LLM

## Watermark detector — `engines/detector_watermark.py`
- Read-only scan reusing cleaner primitives; emits `WatermarkReport`

## SynthID detector — `engines/detector_synthid.py`

Optional, lazy. Disabled by default. Backed by the Hugging Face Transformers
production class `SynthIDTextWatermarkDetector`.

### Enabling

1. Set environment variable `ENABLE_SYNTHID=true` on the api container.
2. Optionally set `SYNTHID_MODEL` (default: `google/gemma-2b`).
3. Ensure the `hf_cache` volume is mounted (already wired in `docker-compose.yml`).
4. First call triggers a model download into the volume; subsequent calls are warm.

### States returned

- `enabled=False, available=False` — feature flag off (default).
- `enabled=True,  available=False` — transformers not installed, class missing,
  model could not be loaded, or runtime error. `detail` carries the reason.
- `enabled=True,  available=True`  — `score ∈ [0, 1]` populated.

### Testing

Tests inject a fake loader via `detector_synthid._set_loader_for_tests(...)`
so no real model download happens in CI.
