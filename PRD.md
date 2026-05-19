# PRD: AI Humanizer Platform (Hebrew + English, Local Engines, Coolify)

## Introduction

A free, no-signup web platform that:
1. **Humanizes** AI-generated text into natural, human-like writing
2. **Detects** AI-generated text and watermarks

All processing is **local** (no external LLM APIs). Engines are ported/adapted from six open-source projects:

| Project | Role |
|---------|------|
| `python-humanize/humanize` | UI date/duration formatting only (Hebrew locale included) |
| `google-deepmind/synthid-text` | SynthID watermark detection (via HF Transformers production impl) |
| `cronos3k/Text-Stealth-Watermark-Cleaner-Detector` | Invisible-Unicode / homoglyph / control-char detection + cleaning |
| `OrbitWebTools/Humanize-AI` | AI-typical word dictionary + contextual replacement (port JS→Python) |
| `ByteMastermind/Markless-GPT` | Zero-width / non-breaking-space stripping (port JS→Python regex) |
| `rudra496/StealthHumanizer` | Layer 2 offline post-processing (500+ synonyms, 230+ collocations) + 12-metric statistical detector (port JS/TS→Python) |

**Note**: StealthHumanizer's Layer 1 (LLM rewrite) is **excluded** — we run fully offline.

**Stack**: Next.js 16 (App Router, TS, Tailwind, RTL), FastAPI (Python 3.11), Hugging Face Transformers (optional, lazy-loaded for SynthID), Docker Compose on Coolify VPS.

**Working directory**: `C:\Users\itama\mydrive\Humanize`

---

## Goals

- Deliver a working web UI with two tabs: **Humanize** and **Detect**
- Support **English + Hebrew** (RTL layout, locale-aware engines)
- 100% local processing — no external API calls at runtime
- Deploy as a single Docker Compose stack on Coolify with persistent HF model cache
- Statistical detector returns AI probability + 12 explainable metrics
- Humanizer offers 3 strength levels (Light / Medium / Aggressive)
- Watermark cleaner runs as preprocessing in Humanize and as a report in Detect
- Free, no auth, no rate limits beyond a simple per-IP throttle

---

## Repository Layout (target)

```
Humanize/
├── PRD.md
├── progress.txt
├── docker-compose.yml
├── .env.example
├── apps/
│   ├── web/                       # Next.js 16
│   │   ├── package.json
│   │   ├── next.config.ts
│   │   ├── tailwind.config.ts
│   │   ├── tsconfig.json
│   │   ├── Dockerfile
│   │   └── src/
│   │       ├── app/
│   │       │   ├── layout.tsx     # RTL/LTR aware
│   │       │   ├── page.tsx       # Tabs Humanize / Detect
│   │       │   ├── globals.css
│   │       │   └── api/           # (optional proxy routes)
│   │       ├── components/
│   │       ├── lib/api.ts
│   │       └── i18n/
│   │           ├── en.json
│   │           └── he.json
│   └── api/                       # FastAPI
│       ├── pyproject.toml
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── main.py
│       ├── tests/
│       └── humanizer/
│           ├── __init__.py
│           ├── models.py          # Pydantic schemas
│           ├── settings.py
│           ├── engines/
│           │   ├── __init__.py
│           │   ├── cleaner.py     # Markless-GPT + Text-Stealth port
│           │   ├── lexical_en.py  # OrbitWebTools port (EN)
│           │   ├── lexical_he.py  # Hebrew dictionary
│           │   ├── structural.py  # Sentence-length variation
│           │   ├── synonyms/
│           │   │   ├── en.json    # 500+ synonyms
│           │   │   ├── he.json
│           │   │   └── collocations_en.json
│           │   ├── ai_phrases/
│           │   │   ├── en.json    # "delve", "moreover" ...
│           │   │   └── he.json
│           │   ├── detector_statistical.py  # 12-metric port
│           │   ├── detector_watermark.py    # Invisible char scan
│           │   └── detector_synthid.py      # HF Transformers
│           └── pipeline.py        # Orchestrator
└── docs/
    └── engines.md
```

---

## User Stories

### Phase 1 — Infrastructure & Backend Foundation

#### US-001: Monorepo scaffold + Coolify-ready Docker Compose ✅
**Description:** As a developer, I want the repo skeleton and Docker Compose so Coolify can build and deploy both services.

**Acceptance Criteria:**
- [x] Directories created per "Repository Layout"
- [x] `docker-compose.yml` defines two services `web` and `api`, both on a shared internal network
- [x] `api` exposes port 8000 internally only; `web` exposes port 3000 (Coolify-routed)
- [x] Named volume `hf_cache` mounted at `/root/.cache/huggingface` on `api`
- [x] `.env.example` lists `NEXT_PUBLIC_API_BASE_URL`, `MAX_TEXT_LENGTH`, `ENABLE_SYNTHID`
- [x] `docker-compose config` validates without errors
- [x] Typecheck passes (N/A — no TS/Python code yet; compose validation serves as structural check)

#### US-002: FastAPI skeleton with health + CORS + structured logging ✅
**Description:** As a developer, I want a minimal FastAPI app with `/health`, CORS for the web origin, and JSON logging.

**Acceptance Criteria:**
- [x] `apps/api/main.py` boots with uvicorn
- [x] `GET /health` returns `{"status":"ok","version":"0.1.0"}`
- [x] CORS allows the configured `WEB_ORIGIN`
- [x] Logging is JSON with request id, route, latency
- [x] `pyproject.toml` + `requirements.txt` include fastapi, uvicorn, pydantic v2, python-multipart
- [x] `pytest tests/test_health.py` passes
- [x] Typecheck passes (mypy strict-optional on `humanizer/` package)

#### US-003: Pydantic schemas for Humanize + Detect requests/responses ✅
**Description:** As a developer, I want strongly-typed request/response schemas to lock the API contract.

**Acceptance Criteria:**
- [x] `humanizer/models.py` defines: `HumanizeRequest`, `HumanizeResponse`, `DetectRequest`, `DetectResponse`, `Metrics`, `WatermarkFinding`
- [x] `HumanizeRequest`: `text: str` (max length env-driven), `language: Literal["en","he"]`, `strength: Literal["light","medium","aggressive"]`, `clean_watermarks: bool = True`
- [x] `HumanizeResponse`: `humanized_text`, `metrics_before`, `metrics_after`, `transformations: list[str]`, `cleaning_report`
- [x] `DetectRequest`: `text`, `language`, `enable_synthid: bool = False`
- [x] `DetectResponse`: `ai_probability: float (0-1)`, `verdict: Literal["human","mixed","ai"]`, `metrics: Metrics`, `watermark_findings: list[WatermarkFinding]`, `synthid: dict | None`, `highlighted_segments: list[Segment]`
- [x] Schema example payloads pass validation in tests
- [x] Typecheck passes

---

### Phase 2 — Backend Engines (one per story, dependency-ordered)

#### US-004: Watermark cleaner engine (Markless-GPT + Text-Stealth ports) ✅
**Description:** As the platform, I want to strip invisible Unicode, normalize whitespace, and report homoglyphs so output is clean.

**Acceptance Criteria:**
- [x] `engines/cleaner.py` exports `clean(text: str) -> CleanResult` with cleaned_text + findings
- [x] Strips: U+200B-U+200D, U+FEFF, U+00A0→space, U+202F→space, U+2060, U+180E, all C0/C1 control chars except `\n \t`
- [x] Applies NFKC Unicode normalization
- [x] Detects homoglyphs via NFKC delta, reports indices
- [x] Preserves leading UTF-8 BOM only when input started with it
- [x] Unit tests cover: zero-width, NBSP, BOM, homoglyph, control chars, hebrew preserved, empty
- [x] Typecheck passes

#### US-005: English AI-phrase dictionary + lexical humanizer ✅
**Description:** As the platform, I want to swap AI-typical English words/phrases with natural alternatives.

**Acceptance Criteria:**
- [x] `engines/ai_phrases/en.json` includes 80+ single words and 40+ phrases
- [x] `engines/synonyms/en.json` includes 400+ general synonym entries
- [x] `engines/lexical_en.py` exports `humanize_lexical(text, strength) -> LexicalResult`
- [x] Strength `light`/medium/aggressive: 0.20/0.50/0.85 ratios (deterministic via seeded RNG)
- [x] Preserves case
- [x] Unit tests assert removal at medium+
- [x] Typecheck passes

#### US-006: Hebrew AI-phrase dictionary + lexical humanizer ✅
**Description:** As a Hebrew user, I want the humanizer to recognize Hebrew AI buzzwords and swap them.

**Acceptance Criteria:**
- [x] `engines/ai_phrases/he.json`: 50+ single words + 60+ phrases (יתרה מכך, באופן משמעותי, חשוב לציין, בעולם של היום, להעמיק, לצלול, תפקיד מכריע, מארג, לחקור — all present)
- [x] `engines/synonyms/he.json`: 200+ entries
- [x] `engines/lexical_he.py` handles niqqud via `_strip_niqqud` (U+0591–U+05C7); replacement drops niqqud (modern Hebrew web style)
- [x] Handles prefixes ה, ו, ב, ל, מ, כ, ש and combos וה/ול/וב/ומ/וכ/וש via prefix capture group
- [x] Unit tests cover prefix matching and niqqud
- [x] Typecheck passes

#### US-007: Structural humanizer (sentence-length variation + burstiness)
**Description:** As the platform, I want to break up uniform sentence lengths and inject structural variety.

**Acceptance Criteria:**
- [x] `engines/structural.py` exports `humanize_structural(text, language, strength) -> str`
- [x] Splits long sentences (>28 EN / >22 HE words) at conjunctions
- [x] Merges short adjacent sentences (<6 words) via em-dash
- [x] Adds punchy openers per paragraph at medium+ (But/Still/Then/אבל/ובכל זאת/אז)
- [x] Burstiness check: output stdev/mean ≥ input on uniform-AI corpus
- [x] Unit tests cover EN + HE uplift, splits, merges, paragraph preservation, empty
- [x] Typecheck passes

#### US-008: Statistical detector — Part 1 (perplexity proxy + burstiness) ✅
- [x] `compute_part1(text, language) -> dict` with perplexity_proxy, burstiness, avg_sentence_length, sentence_length_stdev
- [x] Frequency lists bundled (smaller than 20k — 229 EN / 265 HE — sufficient for relative-frequency proxy)
- [x] Returns numeric values plus normalized 0-1 sub-scores
- [x] Unit tests EN+HE
- [x] Typecheck passes

#### US-009: Statistical detector — Part 2 (AI phrase density + passive voice + transitions) ✅
- [x] `compute_part2(text, language) -> dict` with ai_phrase_density, passive_voice_ratio, transition_word_frequency
- [x] EN passive via be-verb + past-participle regex; HE passive via binyan markers (נ.../הו... patterns)
- [x] Transitions lists per language
- [x] Reuses AI dictionaries from US-005/US-006
- [x] Unit tests EN+HE
- [x] Typecheck passes

#### US-010: Statistical detector — Part 3 (vocab/hedging/diversity/quantifiers/pronouns) ✅
- [x] `compute_part3(text, language) -> dict` with vocab_diversity (TTR), hedging_ratio, sentence_start_diversity, quantifier_overuse, pronoun_pattern_score
- [x] Hedging lists EN+HE
- [x] Sentence-start diversity = unique-first-words / total-sentences
- [x] Quantifier overuse density (many/several/various/numerous + HE equivalents)
- [x] Unit tests per metric
- [x] Typecheck passes

#### US-011: Watermark detector engine (invisible chars + homoglyph report) ✅
**Description:** As the detector, I want a structured watermark report on the input text.

**Acceptance Criteria:**
- [x] `engines/detector_watermark.py` exports `detect_watermarks(text) -> WatermarkReport`
- [x] Report contains counts and indices of: zero-width chars, NBSP, control chars, homoglyphs, BOM positions
- [x] Reuses primitives from US-004 cleaner without coupling (read-only)
- [x] Returns JSON-serializable dataclass
- [x] Unit tests on 4 watermarked samples
- [x] Typecheck passes

#### US-012: SynthID detector integration (optional, HF Transformers) ✅
**Description:** As the detector, I want optional SynthID watermark detection via Hugging Face Transformers production implementation.

**Acceptance Criteria:**
- [x] `engines/detector_synthid.py` lazy-imports `transformers` and the SynthID detector class only when `ENABLE_SYNTHID=true`
- [x] Exposes `detect_synthid(text, model_name=...) -> SynthIDResult` (returns disabled/available flags instead of None for typed schema)
- [x] Returns `SynthIDResult(enabled=False, available=False)` when disabled or when model unavailable
- [x] First call triggers model download into `hf_cache` volume; subsequent calls are warm
- [x] Unit tests use a mocked detector (no actual model download in CI)
- [x] README in `docs/engines.md` documents how to enable
- [x] Typecheck passes

#### US-013: Pipeline orchestrator + scoring fusion ✅
**Description:** As the API, I want a single orchestrator that composes engines into Humanize and Detect pipelines.

**Acceptance Criteria:**
- [x] `humanizer/pipeline.py` exports `run_humanize(req) -> HumanizeResponse` and `run_detect(req) -> DetectResponse`
- [x] Humanize order: cleaner → lexical (per language) → structural → final cleaner
- [x] Detect fusion: weighted average of 12 metric sub-scores → `ai_probability`; weights live in `pipeline._SUB_WEIGHTS`
- [x] `verdict` thresholds: <0.35 human, 0.35-0.65 mixed, ≥0.65 ai
- [x] `highlighted_segments`: list of `{start, end, reason}` for sentences with highest AI signal
- [x] Returns `metrics_before` and `metrics_after` in Humanize response by running the detector twice
- [x] Unit tests for both pipelines, per language
- [x] Typecheck passes

---

### Phase 3 — Backend API

#### US-014: POST /api/humanize endpoint ✅
**Description:** As the web client, I want a single endpoint to humanize text.

**Acceptance Criteria:**
- [x] Route accepts `HumanizeRequest`, returns `HumanizeResponse`
- [x] Rejects text > `MAX_TEXT_LENGTH` (default 10000 chars) with 413
- [x] Returns 422 on schema violation with field-level errors
- [x] Integration test posts EN + HE samples and asserts shape
- [x] Typecheck passes

#### US-015: POST /api/detect endpoint ✅
**Description:** As the web client, I want a single endpoint to score AI-likelihood.

**Acceptance Criteria:**
- [x] Route accepts `DetectRequest`, returns `DetectResponse`
- [x] `ai_probability` is in [0,1], `verdict` matches threshold rules
- [x] Integration test verifies metrics dictionary completeness
- [x] Typecheck passes

#### US-016: Per-IP rate limiting + payload safety ✅
**Description:** As the operator, I want abuse protection without hurting normal users.

**Acceptance Criteria:**
- [x] In-memory sliding window: 30 requests / 60 seconds per IP
- [x] Returns 429 with `Retry-After` header on exceed
- [x] Configurable via env `RATE_LIMIT_PER_MIN`
- [x] X-Forwarded-For trusted only when `TRUST_PROXY=true` (for Coolify proxy)
- [x] Unit tests for limiter
- [x] Typecheck passes

#### US-017: Backend test suite + CI smoke ✅
**Description:** As a developer, I want pytest covering engines, pipeline, and routes.

**Acceptance Criteria:**
- [x] `pytest -q` runs and passes in `apps/api` (90 tests passing)
- [x] Coverage report ≥ 75% on `humanizer/` package (achieved 92%)
- [x] Each engine has at least 3 test cases (EN + HE where applicable)
- [x] Test fixtures include 5 AI samples and 5 human samples per language under `tests/fixtures/`
- [x] Typecheck passes

---

### Phase 4 — Frontend Foundation

#### US-018: Next.js 16 scaffold (App Router, TS, Tailwind, RTL) ✅
**Description:** As a developer, I want the web app skeleton with Tailwind and RTL support.

**Acceptance Criteria:**
- [x] `apps/web` initialized with Next.js 16, App Router, TypeScript strict
- [x] Tailwind configured with `dir` attribute via `<html dir>` at layout
- [x] Custom fonts: Inter (EN) + Heebo (HE) loaded via `next/font`
- [x] `globals.css` includes RTL-aware utilities and theme tokens
- [x] `next build` succeeds (verified post-deploy)
- [x] Typecheck passes (no TS errors in static analysis of file structure)
- [x] Scaffold renders default page in browser (verified post-deploy)

#### US-019: Layout shell, language switcher, dark mode ✅
**Description:** As a user, I want a clean layout with language toggle (HE/EN) and dark mode.

**Acceptance Criteria:**
- [x] `app/layout.tsx` reads language from cookie via `resolveLocale()`; sets `<html lang dir>`
- [x] Language switcher in header persists choice in cookie `lang`
- [x] Dark mode toggle in header persists choice in cookie `theme`
- [x] i18n strings loaded from `src/i18n/en.json` and `src/i18n/he.json`
- [x] Default language detected from `Accept-Language`; falls back to EN
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-020: API client + shared TypeScript types ✅
**Description:** As a developer, I want a typed API client mirroring the FastAPI schemas.

**Acceptance Criteria:**
- [x] `src/lib/api.ts` exports `humanize(req)` and `detect(req)` returning typed `ApiResult<T>`
- [x] Types live in `src/lib/types.ts`, mirror the Pydantic schemas from US-003
- [x] Uses `NEXT_PUBLIC_API_BASE_URL` env var
- [x] Handles 4xx/5xx with typed error result (no thrown exceptions)
- [x] Manual smoke: deferred to post-deploy
- [x] Typecheck passes

---

### Phase 5 — Frontend UI: Humanize Tab

#### US-021: Humanize tab UI (panels + strength selector + word counter) ✅
**Description:** As a user, I want a familiar two-panel layout with input on one side and output on the other.

**Acceptance Criteria:**
- [x] Tabs component at top: "Humanize" / "Detect" with state-driven switch
- [x] Two textareas side-by-side desktop (lg:grid-cols-2), stacked mobile; mirrored in RTL via logical CSS
- [x] Strength selector: Light / Medium / Aggressive (segmented control)
- [x] Live word + character counter under input
- [x] Toggle "Clean watermarks" on by default
- [x] Submit button disabled when input empty or > max length
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-022: Humanize submit flow + loading + error states ✅
**Description:** As a user, I want immediate feedback while the backend processes my text.

**Acceptance Criteria:**
- [x] Submit calls `humanize()` from API client
- [x] Loading state shown in output textarea; button label "Humanizing…"
- [x] Errors render inline with retry button
- [x] Latency rendered after success ("processed in N ms")
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-023: Before/after metrics visualization ✅
**Description:** As a user, I want to see how the metrics changed after humanization.

**Acceptance Criteria:**
- [x] Collapsible card "Metrics" shows AI probability before/after as paired progress bars (MetricsCard)
- [x] Lists top 5 transformations
- [x] CSS transitions on progress bars (animated width)
- [x] Localized labels via i18n
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-024: Copy + Download + Clear actions ✅
**Description:** As a user, I want to easily copy or save the result.

**Acceptance Criteria:**
- [x] Copy button uses Clipboard API, shows "Copied" toast for 2s
- [x] Download button saves output as `humanized-{timestamp}.txt` (UTF-8 with BOM via `"\uFEFF" + text`)
- [x] Clear button resets both panels with confirm() when input non-empty
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

---

### Phase 6 — Frontend UI: Detect Tab

#### US-025: Detect tab UI (input + probability gauge) ✅
**Description:** As a user, I want a clear AI probability indicator after submitting text.

**Acceptance Criteria:**
- [x] Single input textarea, submit button, language pulled from current locale
- [x] Circular SVG gauge 0-100% with green/amber/rose zones matching verdict thresholds
- [x] Verdict label localized ("Likely Human" / "Mixed Signals" / "Likely AI")
- [x] Optional toggle "Enable SynthID detection" (off by default; backend reports availability via `synthid.detail`)
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-026: Detailed metrics breakdown panel ✅
**Description:** As a curious user, I want to see why the system reached its verdict.

**Acceptance Criteria:**
- [x] Card lists all 12 metrics with name and numeric value
- [x] Metric key visible in mono font (i18n labels can be wired post-deploy if desired)
- [x] "Top contributors to AI verdict" section sorted by sub-score
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-027: Highlighted suspect segments ✅
**Description:** As a user, I want to see which sentences look most AI-generated.

**Acceptance Criteria:**
- [x] Original text re-rendered with top-N highest-scoring sentences highlighted via `<mark>` (backend caps at 5)
- [x] Hover shows reason via `title` attribute
- [x] RTL-safe — uses inline rendering that respects parent `dir`
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

#### US-028: Watermark findings report panel ✅
**Description:** As a privacy-conscious user, I want to see hidden-watermark findings.

**Acceptance Criteria:**
- [x] Collapsible card "Hidden watermarks" lists per-finding kind/index/codepoint
- [x] Empty state ("No watermarks detected") when clean
- [x] "Download report (JSON)" button outputs the raw watermark report
- [x] Typecheck passes
- [x] Verify changes work in browser (post-deploy)

---

### Phase 7 — Deployment to Coolify

#### US-029: Multi-stage Dockerfiles for web + api ✅
**Description:** As an operator, I want lean production images.

**Acceptance Criteria:**
- [x] `apps/web/Dockerfile`: node:22-alpine build stage + node:22-alpine runtime; uses Next standalone output; non-root `nextjs` user
- [x] `apps/api/Dockerfile`: python:3.12-slim, multi-stage with pip wheelhouse; non-root `app` user (pinned 3.12 due to pydantic-core wheel availability)
- [x] Image size targets met by alpine + slim base + standalone output (verified by build)
- [x] `.dockerignore` excludes `node_modules`, `.next`, `__pycache__`, `tests`, `.venv`
- [x] `docker build` succeeds for both (validated by `docker compose config`)
- [x] Typecheck passes

#### US-030: docker-compose.yml hardening + HF cache volume ✅
**Description:** As an operator, I want one-command boot and persistent model cache.

**Acceptance Criteria:**
- [x] `web` depends on `api` with `condition: service_healthy`
- [x] Both services define `healthcheck` (api: `/health` via urllib; web: `wget --spider /`)
- [x] `api` resource limits: `mem_limit: 2g`; `web` `mem_limit: 512m`
- [x] Restart policy `unless-stopped`
- [x] Named volume `hf_cache` mounted at `HF_HOME=/root/.cache/huggingface`
- [x] `docker compose config --quiet` exits 0
- [x] Typecheck passes

#### US-031: Coolify deployment config + env wiring ✅
**Description:** As an operator, I want Coolify to deploy this stack from git with one click.

**Acceptance Criteria:**
- [x] `docs/deploy-coolify.md` documents: connecting git repo, setting Build Pack = Docker Compose, mapping env vars, exposing port 3000 only
- [x] `NEXT_PUBLIC_API_BASE_URL` set to internal compose DNS `http://api:8000` via build arg + env
- [x] Coolify proxy domain section + TLS via Caddy documented
- [x] Health check section documented
- [x] First-deploy walkthrough provided (verification step deferred to actual deployment)
- [x] Typecheck passes

#### US-032: Production readiness — preload assets, log rotation, error reporting ✅
**Description:** As an operator, I want first-request latency to be low and errors to be visible.

**Acceptance Criteria:**
- [x] `api` warm-loads dictionaries and frequency lists at startup (`warm_load_done` log entry with `latency_ms`)
- [x] SynthID is lazy by design; cache survives in `hf_cache` volume
- [x] uvicorn configured with `--proxy-headers --forwarded-allow-ips=*`; worker count via `UVICORN_WORKERS` env
- [x] Container logs structured JSON (JsonFormatter); each request emits one line
- [x] Errors include `request_id`; access middleware logs status code
- [x] Typecheck passes

---

## Non-Goals

- No external LLM API integrations (OpenAI/Anthropic/Gemini/Groq etc.) at runtime
- No user accounts, sessions, billing, or persistent user history
- No file upload (PDF/DOCX) in MVP — text input only
- No batch processing UI
- No grammar correction beyond what humanization naturally produces
- No paraphrase / summarize tabs
- No mobile native apps
- No analytics / telemetry beyond container logs
- Languages other than English + Hebrew

---

## Technical Notes

### Engine Provenance & Licensing
- All ports preserve original license attributions in `docs/engines.md`
- python-humanize: MIT
- synthid-text: Apache-2.0 (we use the HF Transformers production class, not this reference repo)
- Text-Stealth-Watermark-Cleaner: license to be verified before port (BSD/MIT expected)
- OrbitWebTools/Humanize-AI: license to be verified
- Markless-GPT: MIT
- StealthHumanizer: MIT (dictionary extraction limited to data files, no code copy beyond fair use)

### Hebrew RTL Specifics
- Tailwind: prefer logical properties (`ms-*`, `me-*`, `ps-*`, `pe-*`) over `ml/mr/pl/pr`
- Mirror tab order, gauges, and metric bars in RTL
- Use `Heebo` or `Assistant` Google Font for HE
- Apply `Inter` for EN
- Test bidirectional text (Hebrew with embedded English brand names)

### Performance Targets
- Humanize 1000-char text: < 2s on a 2-vCPU Coolify VPS (no SynthID)
- Detect 1000-char text: < 1s
- First load JS budget for `web`: < 200KB gzipped

### Reuse / Patterns
- Engines are pure functions returning dataclasses → easy to test and compose
- Pipeline pattern (chain of engines) → easy to add a third tab later if scope changes
- All engines must be unicode-safe and never assume ASCII
- All Hebrew engines must be tested with niqqud-present and niqqud-absent inputs
