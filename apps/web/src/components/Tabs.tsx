"use client";

import { useState } from "react";
import type { Dict, Locale } from "@/i18n";
import { HumanizePanel } from "./HumanizePanel";
import { DetectPanel } from "./DetectPanel";

type Tab = "humanize" | "detect";

interface TabsProps {
  locale: Locale;
  dict: Dict;
}

export function Tabs({ locale, dict }: TabsProps) {
  const [active, setActive] = useState<Tab>("humanize");

  return (
    <div className="space-y-6">
      <div
        role="tablist"
        aria-label="Mode"
        className="inline-flex rounded-lg border border-[rgb(var(--border))] p-1"
      >
        {(["humanize", "detect"] as const).map((tab) => {
          const selected = active === tab;
          return (
            <button
              key={tab}
              role="tab"
              type="button"
              aria-selected={selected}
              onClick={() => setActive(tab)}
              className={
                "rounded-md px-4 py-1.5 text-sm font-medium transition " +
                (selected
                  ? "bg-brand text-white"
                  : "text-[rgb(var(--muted))] hover:bg-[rgb(var(--surface))]")
              }
            >
              {dict.tabs[tab]}
            </button>
          );
        })}
      </div>
      {active === "humanize" ? (
        <HumanizePanel locale={locale} dict={dict} />
      ) : (
        <DetectPanel locale={locale} dict={dict} />
      )}
    </div>
  );
}
