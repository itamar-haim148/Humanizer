/**
 * Mirrors `apps/api/humanizer/models.py`. Keep in sync.
 */

export type Language = "en" | "he";
export type Strength = "light" | "medium" | "aggressive";
export type Verdict = "human" | "mixed" | "ai";

export type WatermarkKind =
  | "zero_width"
  | "nbsp"
  | "control_char"
  | "homoglyph"
  | "bom"
  | "non_standard_space";

export interface WatermarkFinding {
  kind: WatermarkKind;
  char: string;
  codepoint: string;
  index: number;
  note: string | null;
}

export interface CleaningReport {
  removed_count: number;
  normalized_count: number;
  findings: WatermarkFinding[];
}

export interface Metrics {
  perplexity_proxy: number;
  burstiness: number;
  ai_phrase_density: number;
  passive_voice_ratio: number;
  transition_word_frequency: number;
  vocab_diversity: number;
  hedging_ratio: number;
  sentence_start_diversity: number;
  quantifier_overuse: number;
  pronoun_pattern_score: number;
  avg_sentence_length: number;
  sentence_length_stdev: number;
  ai_probability: number;
  verdict: Verdict;
}

export interface Segment {
  start: number;
  end: number;
  text: string;
  sub_score: number;
  reason: string;
}

export interface SynthIDResult {
  enabled: boolean;
  available: boolean;
  score: number | null;
  detail: string | null;
}

export interface HumanizeRequest {
  text: string;
  language: Language;
  strength: Strength;
  clean_watermarks?: boolean;
}

export interface HumanizeResponse {
  humanized_text: string;
  metrics_before: Metrics;
  metrics_after: Metrics;
  transformations: string[];
  cleaning_report: CleaningReport;
  language: Language;
  strength: Strength;
  latency_ms: number;
}

export interface DetectRequest {
  text: string;
  language: Language;
  enable_synthid?: boolean;
}

export interface DetectResponse {
  ai_probability: number;
  verdict: Verdict;
  metrics: Metrics;
  watermark_findings: WatermarkFinding[];
  synthid: SynthIDResult | null;
  highlighted_segments: Segment[];
  language: Language;
  latency_ms: number;
}

export interface ApiError {
  ok: false;
  status: number;
  message: string;
  detail?: unknown;
}

export type ApiResult<T> = { ok: true; data: T } | ApiError;
