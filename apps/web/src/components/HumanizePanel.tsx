"use client";

import { useMemo, useState } from "react";
import type { Dict, Locale } from "@/i18n";
import { formatString } from "@/i18n";
import { humanize } from "@/lib/api";
import type {
  HumanizeResponse,
  Strength,
} from "@/lib/types";
import { FormattedOutput } from "./FormattedOutput";
import { MetricsCard } from "./MetricsCard";

interface Props {
  locale: Locale;
  dict: Dict;
}

const MAX = 10_000;

export function HumanizePanel({ locale, dict }: Props) {
  const [input, setInput] = useState("");
  const [strength, setStrength] = useState<Strength>("medium");
  const [clean, setClean] = useState(true);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<HumanizeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wordCount = useMemo(
    () => (input.trim() ? input.trim().split(/\s+/).length : 0),
    [input],
  );
  const charCount = input.length;
  const tooLong = charCount > MAX;
  const disabled = loading || !input.trim() || tooLong;

  async function onSubmit() {
    setLoading(true);
    setError(null);
    setResp(null);
    const result = await humanize({
      text: input,
      language: locale,
      strength,
      clean_watermarks: clean,
    });
    setLoading(false);
    if (!result.ok) {
      setError(
        result.status === 413
          ? dict.errors.tooLong
          : result.status === 0
            ? dict.errors.generic
            : `${dict.errors.generic} (${result.status})`,
      );
      return;
    }
    setResp(result.data);
  }

  function onClear() {
    if (input.trim() && !confirm(locale === "he" ? "לנקות הכל?" : "Clear everything?")) return;
    setInput("");
    setResp(null);
    setError(null);
  }

  return (
    <section className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="surface space-y-2 rounded-lg p-4">
          <label className="block text-sm font-medium" htmlFor="hum-input">
            {dict.humanize.inputLabel}
          </label>
          <textarea
            id="hum-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={14}
            className="w-full resize-y rounded-md border border-[rgb(var(--border))] bg-transparent p-3 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
            placeholder={dict.humanize.inputLabel}
          />
          <div className="flex justify-between text-xs muted">
            <span>{formatString(dict.humanize.wordCount, { count: wordCount })}</span>
            <span className={tooLong ? "text-red-500" : undefined}>
              {formatString(dict.humanize.charCount, { count: charCount })} / {MAX}
            </span>
          </div>
        </div>

        <div className="surface space-y-2 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <label className="block text-sm font-medium" htmlFor="hum-output">
              {dict.humanize.outputLabel}
            </label>
            {resp ? (
              <span className="text-xs muted">
                {formatString(dict.humanize.latency, { ms: resp.latency_ms.toFixed(1) })}
              </span>
            ) : null}
          </div>
          <FormattedOutput
            id="hum-output"
            value={resp?.humanized_text ?? ""}
            loading={loading}
            dict={dict}
            fileBaseName="humanized"
          />
          {error ? (
            <div className="space-y-2 rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-900/30 dark:text-red-200">
              <div>{error}</div>
              <button
                type="button"
                onClick={onSubmit}
                className="rounded-md bg-red-600 px-3 py-1 text-xs font-medium text-white"
              >
                {dict.errors.retry}
              </button>
            </div>
          ) : null}
          <button
            type="button"
            onClick={onClear}
            className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm"
          >
            {dict.humanize.clear}
          </button>
        </div>
      </div>

      <div className="surface flex flex-wrap items-center gap-4 rounded-lg p-4">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium">{dict.humanize.strength}:</span>
          <div className="inline-flex rounded-md border border-[rgb(var(--border))] p-0.5">
            {(["light", "medium", "aggressive"] as const).map((s) => (
              <button
                key={s}
                type="button"
                aria-pressed={strength === s}
                onClick={() => setStrength(s)}
                className={
                  "rounded px-3 py-1 text-sm " +
                  (strength === s
                    ? "bg-brand text-white"
                    : "text-[rgb(var(--muted))]")
                }
              >
                {dict.humanize[`strength${s[0].toUpperCase() + s.slice(1)}` as
                  | "strengthLight"
                  | "strengthMedium"
                  | "strengthAggressive"]}
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={clean}
            onChange={(e) => setClean(e.target.checked)}
          />
          {dict.humanize.cleanWatermarks}
        </label>
        <div className="ms-auto">
          <button
            type="button"
            onClick={onSubmit}
            disabled={disabled}
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-dark disabled:opacity-50"
          >
            {loading ? dict.humanize.submitting : dict.humanize.submit}
          </button>
        </div>
      </div>

      {resp ? (
        <MetricsCard
          title={dict.humanize.metricsTitle}
          before={resp.metrics_before}
          after={resp.metrics_after}
          transformations={resp.transformations.slice(0, 5)}
          dict={dict}
        />
      ) : null}
    </section>
  );
}
