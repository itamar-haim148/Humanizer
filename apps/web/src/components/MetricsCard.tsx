"use client";

import type { Dict } from "@/i18n";
import type { Metrics } from "@/lib/types";

interface Props {
  title: string;
  before: Metrics;
  after: Metrics;
  transformations: string[];
  dict: Dict;
}

function ProbabilityBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  const tone =
    value < 0.35 ? "bg-emerald-500" : value < 0.65 ? "bg-amber-500" : "bg-rose-500";
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs">
        <span>{label}</span>
        <span className="font-mono">{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-[rgb(var(--surface))]">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function MetricsCard({ title, before, after, transformations, dict }: Props) {
  return (
    <details className="surface rounded-lg p-4" open>
      <summary className="cursor-pointer text-sm font-semibold">{title}</summary>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ProbabilityBar
          label={`${dict.humanize.aiProbability} — before`}
          value={before.ai_probability}
        />
        <ProbabilityBar
          label={`${dict.humanize.aiProbability} — after`}
          value={after.ai_probability}
        />
      </div>
      {transformations.length > 0 ? (
        <div className="mt-4">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide muted">
            {dict.humanize.topTransformations}
          </h4>
          <ul className="space-y-1 text-sm">
            {transformations.map((t, i) => (
              <li key={i} className="font-mono text-xs muted">
                {t}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </details>
  );
}
