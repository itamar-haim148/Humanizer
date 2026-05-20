"use client";

import { useEffect, useMemo, useState } from "react";
import type { Dict, Locale } from "@/i18n";
import { formatString } from "@/i18n";
import { humanizeLLM, makeBasicAuth } from "@/lib/api";
import type { HumanizeLLMResponse, Strength } from "@/lib/types";
import { MetricsCard } from "./MetricsCard";

interface Props {
  locale: Locale;
  dict: Dict;
}

const MAX = 10_000;
const SESSION_KEY = "humanize.llm.auth";

export function LLMPanel({ locale, dict }: Props) {
  // ---------- auth state ----------
  const [auth, setAuth] = useState<string | null>(null);
  const [user, setUser] = useState("");
  const [pass, setPass] = useState("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [authChecking, setAuthChecking] = useState(false);

  // ---------- humanize state ----------
  const [input, setInput] = useState("");
  const [strength, setStrength] = useState<Strength>("medium");
  const [clean, setClean] = useState(true);
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<HumanizeLLMResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const stored = sessionStorage.getItem(SESSION_KEY);
    if (stored) setAuth(stored);
  }, []);

  const wordCount = useMemo(
    () => (input.trim() ? input.trim().split(/\s+/).length : 0),
    [input],
  );
  const charCount = input.length;
  const tooLong = charCount > MAX;
  const disabled = loading || !input.trim() || tooLong;
  const displayUser = useMemo(() => {
    if (!auth) return "";
    try {
      return atob(auth.slice(6)).split(":")[0] ?? "";
    } catch {
      return "";
    }
  }, [auth]);

  async function onSignIn() {
    setAuthError(null);
    if (!user || !pass) return;
    setAuthChecking(true);
    const basic = makeBasicAuth(user, pass);
    // Probe with a minimal request. 401 = bad creds; 503 = not configured;
    // 422 (validation), 200, 502, 413 all mean creds are OK.
    const result = await humanizeLLM(
      { text: "hi", language: locale, strength: "light" },
      basic,
    );
    setAuthChecking(false);
    if (!result.ok && result.status === 401) {
      setAuthError(dict.llm.invalidCreds);
      return;
    }
    if (!result.ok && result.status === 503) {
      setAuthError(dict.llm.notConfigured);
      return;
    }
    // Any other status means creds passed the auth gate.
    sessionStorage.setItem(SESSION_KEY, basic);
    setAuth(basic);
    setUser("");
    setPass("");
  }

  function onLogout() {
    sessionStorage.removeItem(SESSION_KEY);
    setAuth(null);
    setResp(null);
    setError(null);
  }

  async function onSubmit() {
    if (!auth) return;
    setLoading(true);
    setError(null);
    setResp(null);
    const result = await humanizeLLM(
      {
        text: input,
        language: locale,
        strength,
        clean_watermarks: clean,
      },
      auth,
    );
    setLoading(false);
    if (!result.ok) {
      if (result.status === 401) {
        // Session likely revoked — bounce to login.
        onLogout();
        setAuthError(dict.llm.invalidCreds);
        return;
      }
      if (result.status === 503) {
        setError(dict.llm.notConfigured);
        return;
      }
      if (result.status === 502) {
        setError(dict.llm.gemini502);
        return;
      }
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

  function onCopy() {
    if (!resp) return;
    void navigator.clipboard.writeText(resp.humanized_text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  function onDownload() {
    if (!resp) return;
    const blob = new Blob(["\uFEFF" + resp.humanized_text], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `humanized-llm-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------- render: login ----------
  if (!auth) {
    return (
      <section className="space-y-4">
        <div className="surface rounded-lg p-4 text-sm">
          <h2 className="mb-1 text-base font-semibold">{dict.llm.title}</h2>
          <p className="muted">{dict.llm.description}</p>
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void onSignIn();
          }}
          className="surface max-w-md space-y-3 rounded-lg p-4"
        >
          <h3 className="text-sm font-semibold">{dict.llm.loginTitle}</h3>
          <div>
            <label className="block text-xs font-medium" htmlFor="llm-user">
              {dict.llm.user}
            </label>
            <input
              id="llm-user"
              type="text"
              autoComplete="username"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              className="mt-1 w-full rounded-md border border-[rgb(var(--border))] bg-transparent p-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
            />
          </div>
          <div>
            <label className="block text-xs font-medium" htmlFor="llm-pass">
              {dict.llm.password}
            </label>
            <input
              id="llm-pass"
              type="password"
              autoComplete="current-password"
              value={pass}
              onChange={(e) => setPass(e.target.value)}
              className="mt-1 w-full rounded-md border border-[rgb(var(--border))] bg-transparent p-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand"
            />
          </div>
          {authError ? (
            <div className="rounded-md border border-red-300 bg-red-50 p-2 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-200">
              {authError}
            </div>
          ) : null}
          <button
            type="submit"
            disabled={authChecking || !user || !pass}
            className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-dark disabled:opacity-50"
          >
            {authChecking ? dict.llm.signingIn : dict.llm.signIn}
          </button>
        </form>
      </section>
    );
  }

  // ---------- render: humanize (authed) ----------
  return (
    <section className="space-y-4">
      <div className="surface flex flex-wrap items-center justify-between gap-3 rounded-lg p-3 text-xs">
        <span className="muted">
          {formatString(dict.llm.signedInAs, { user: displayUser })}
        </span>
        <button
          type="button"
          onClick={onLogout}
          className="rounded-md border border-[rgb(var(--border))] px-3 py-1 text-xs"
        >
          {dict.llm.logout}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="surface space-y-2 rounded-lg p-4">
          <label className="block text-sm font-medium" htmlFor="llm-input">
            {dict.humanize.inputLabel}
          </label>
          <textarea
            id="llm-input"
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
            <label className="block text-sm font-medium" htmlFor="llm-output">
              {dict.humanize.outputLabel}
            </label>
            {resp ? (
              <span className="text-xs muted">
                {formatString(dict.humanize.latency, { ms: resp.latency_ms.toFixed(1) })}
              </span>
            ) : null}
          </div>
          <textarea
            id="llm-output"
            value={loading ? "…" : resp?.humanized_text ?? ""}
            readOnly
            rows={14}
            className="w-full resize-y rounded-md border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-3 text-sm"
          />
          {resp ? (
            <div className="flex flex-wrap gap-3 text-xs muted">
              <span>
                {dict.llm.model}: <code>{resp.llm_model}</code>
              </span>
              {resp.llm_prompt_tokens !== null && resp.llm_output_tokens !== null ? (
                <span>
                  {formatString(dict.llm.tokens, {
                    prompt: resp.llm_prompt_tokens,
                    output: resp.llm_output_tokens,
                  })}
                </span>
              ) : null}
            </div>
          ) : null}
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
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={onCopy}
              disabled={!resp}
              className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {copied ? dict.humanize.copied : dict.humanize.copy}
            </button>
            <button
              type="button"
              onClick={onDownload}
              disabled={!resp}
              className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm disabled:opacity-50"
            >
              {dict.humanize.download}
            </button>
          </div>
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
