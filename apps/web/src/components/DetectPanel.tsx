"use client";

import { useMemo, useState } from "react";
import type { Dict, Locale } from "@/i18n";
import { detect } from "@/lib/api";
import type { DetectResponse, Metrics } from "@/lib/types";

interface Props {
  locale: Locale;
  dict: Dict;
}

const MAX = 10_000;

const METRIC_KEYS: ReadonlyArray<keyof Metrics> = [
  "perplexity_proxy",
  "burstiness",
  "ai_phrase_density",
  "passive_voice_ratio",
  "transition_word_frequency",
  "vocab_diversity",
  "hedging_ratio",
  "sentence_start_diversity",
  "quantifier_overuse",
  "pronoun_pattern_score",
  "avg_sentence_length",
  "sentence_length_stdev",
];

function Gauge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value < 0.35 ? "stroke-emerald-500" : value < 0.65 ? "stroke-amber-500" : "stroke-rose-500";
  const circumference = 2 * Math.PI * 45;
  const offset = circumference * (1 - value);
  return (
    <svg viewBox="0 0 100 100" className="h-40 w-40">
      <circle cx="50" cy="50" r="45" className="stroke-[rgb(var(--surface))]" strokeWidth="8" fill="none" />
      <circle
        cx="50"
        cy="50"
        r="45"
        className={tone}
        strokeWidth="8"
        fill="none"
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 50 50)"
      />
      <text
        x="50"
        y="54"
        textAnchor="middle"
        className="fill-current text-2xl font-bold"
      >
        {pct}%
      </text>
    </svg>
  );
}

function highlight(text: string, segments: DetectResponse["highlighted_segments"]) {
  if (segments.length === 0) return text;
  const sorted = [...segments].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((s, i) => {
    if (s.start > cursor) parts.push(text.slice(cursor, s.start));
    parts.push(
      <mark
        key={i}
        title={s.reason}
        className="rounded bg-amber-200/60 px-0.5 dark:bg-amber-500/30"
      >
        {text.slice(s.start, s.end)}
      </mark>,
    );
    cursor = s.end;
  });
  if (cursor < text.length) parts.push(text.slice(cursor));
  return parts;
}

export function DetectPanel({ locale, dict }: Props) {
  const [input, setInput] = useState("");
  const [synthid, setSynthid] = useState(false);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<DetectResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const charCount = input.length;
  const tooLong = charCount > MAX;
  const disabled = loading || !input.trim() || tooLong;

  async function onSubmit() {
    setLoading(true);
    setError(null);
    setResp(null);
    const r = await detect({
      text: input,
      language: locale,
      enable_synthid: synthid,
    });
    setLoading(false);
    if (!r.ok) {
      setError(
        r.status === 413
          ? dict.errors.tooLong
          : `${dict.errors.generic} (${r.status})`,
      );
      return;
    }
    setResp(r.data);
  }

  function downloadReport() {
    if (!resp) return;
    const blob = new Blob([JSON.stringify(resp.watermark_findings, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `watermark-report-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const topContributors = useMemo(() => {
    if (!resp) return [];
    return [
      { name: "AI phrase density", value: resp.metrics.ai_phrase_density },
      { name: "Burstiness (low → AI)", value: 1 - Math.min(1, resp.metrics.burstiness) },
      { name: "Passive voice", value: resp.metrics.passive_voice_ratio },
      { name: "Transitions", value: resp.metrics.transition_word_frequency },
      { name: "Hedging", value: resp.metrics.hedging_ratio },
    ]
      .sort((a, b) => b.value - a.value)
      .slice(0, 3);
  }, [resp]);

  return (
    <section className="space-y-4">
      <div className="surface space-y-2 rounded-lg p-4">
        <label className="block text-sm font-medium" htmlFor="det-input">
          {dict.detect.inputLabel}
        </label>
        <textarea
          id="det-input"
          rows={10}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="w-full resize-y rounded-md border border-[rgb(var(--border))] bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
        />
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={synthid}
              onChange={(e) => setSynthid(e.target.checked)}
            />
            {dict.detect.enableSynthid}
          </label>
          <span className={`ms-auto text-xs muted ${tooLong ? "text-red-500" : ""}`}>
            {charCount} / {MAX}
          </span>
          <button
            type="button"
            onClick={onSubmit}
            disabled={disabled}
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-dark disabled:opacity-50"
          >
            {loading ? dict.detect.submitting : dict.detect.submit}
          </button>
        </div>
        {error ? (
          <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
            {error}
          </div>
        ) : null}
      </div>

      {resp ? (
        <>
          <div className="surface flex flex-col items-center gap-4 rounded-lg p-4 sm:flex-row">
            <Gauge value={resp.ai_probability} />
            <div className="flex-1 space-y-1">
              <div className="text-sm muted">{dict.detect.metricsTitle.split(" ")[0]}</div>
              <div className="text-2xl font-bold">
                {dict.detect.verdict[resp.verdict]}
              </div>
              <div className="text-xs muted">
                {resp.latency_ms.toFixed(1)} ms
              </div>
              {resp.synthid ? (
                <div className="text-xs muted">
                  SynthID:{" "}
                  {resp.synthid.available
                    ? `${Math.round((resp.synthid.score ?? 0) * 100)}%`
                    : resp.synthid.detail ?? "unavailable"}
                </div>
              ) : null}
            </div>
            <div className="flex-1 space-y-2">
              <h4 className="text-xs font-semibold uppercase tracking-wide muted">
                {dict.detect.topContributors}
              </h4>
              <ul className="space-y-1 text-sm">
                {topContributors.map((c) => (
                  <li key={c.name} className="flex justify-between">
                    <span>{c.name}</span>
                    <span className="font-mono">{Math.round(c.value * 100)}%</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <details className="surface rounded-lg p-4" open>
            <summary className="cursor-pointer text-sm font-semibold">
              {dict.detect.metricsTitle}
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {METRIC_KEYS.map((k) => (
                <div key={k} className="flex justify-between rounded border border-[rgb(var(--border))] px-3 py-1.5 text-xs">
                  <span className="font-mono muted">{k}</span>
                  <span className="font-mono">{Number(resp.metrics[k]).toFixed(3)}</span>
                </div>
              ))}
            </div>
          </details>

          {resp.highlighted_segments.length > 0 ? (
            <div className="surface space-y-2 rounded-lg p-4">
              <h4 className="text-sm font-semibold">{dict.detect.suspectSegments}</h4>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {highlight(input, resp.highlighted_segments)}
              </p>
            </div>
          ) : null}

          <details className="surface rounded-lg p-4">
            <summary className="cursor-pointer text-sm font-semibold">
              {dict.detect.watermarksTitle} ({resp.watermark_findings.length})
            </summary>
            {resp.watermark_findings.length === 0 ? (
              <p className="mt-3 text-sm muted">{dict.detect.watermarksEmpty}</p>
            ) : (
              <>
                <ul className="mt-3 space-y-1 text-xs font-mono">
                  {resp.watermark_findings.slice(0, 20).map((f, i) => (
                    <li key={i}>
                      {f.kind} @ {f.index} — {f.codepoint} ({f.note ?? "-"})
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={downloadReport}
                  className="mt-3 rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm"
                >
                  {dict.detect.downloadReport}
                </button>
              </>
            )}
          </details>
        </>
      ) : null}
    </section>
  );
}
