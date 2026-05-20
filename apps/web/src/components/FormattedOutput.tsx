"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Dict } from "@/i18n";
import { copyFormatted } from "@/lib/markdown";

interface Props {
  id: string;
  value: string;
  loading: boolean;
  dict: Dict;
  fileBaseName: string;
}

type ViewMode = "formatted" | "markdown";

/**
 * Output panel that renders the humanizer's Markdown either as styled
 * HTML (default) or as the raw Markdown source in a textarea. Includes
 * "Copy", "Copy with formatting" and "Download" actions.
 *
 * Display rendering goes through `react-markdown` (which builds a React
 * element tree from the Markdown AST and applies `rehype-sanitize`),
 * so untrusted HTML in the source is dropped before reaching the DOM.
 */
export function FormattedOutput({
  id,
  value,
  loading,
  dict,
  fileBaseName,
}: Props) {
  const [view, setView] = useState<ViewMode>("formatted");
  const [plainCopied, setPlainCopied] = useState(false);
  const [richCopied, setRichCopied] = useState(false);
  const [richSupported, setRichSupported] = useState(true);

  useEffect(() => {
    setRichSupported(
      typeof window !== "undefined" &&
        typeof ClipboardItem !== "undefined" &&
        !!navigator.clipboard?.write,
    );
  }, []);

  function onCopyPlain() {
    if (!value) return;
    void navigator.clipboard.writeText(value).then(() => {
      setPlainCopied(true);
      setTimeout(() => setPlainCopied(false), 2000);
    });
  }

  function onCopyRich() {
    if (!value) return;
    void copyFormatted(value).then((ok) => {
      if (!ok) return;
      setRichCopied(true);
      setTimeout(() => setRichCopied(false), 2000);
    });
  }

  function onDownload() {
    if (!value) return;
    const blob = new Blob(["\uFEFF" + value], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileBaseName}-${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const hasContent = !!value && !loading;

  return (
    <>
      <div className="flex items-center justify-between">
        <div className="inline-flex rounded-md border border-[rgb(var(--border))] p-0.5 text-xs">
          {(["formatted", "markdown"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={view === mode}
              onClick={() => setView(mode)}
              className={
                "rounded px-2.5 py-1 " +
                (view === mode
                  ? "bg-brand text-white"
                  : "text-[rgb(var(--muted))]")
              }
            >
              {mode === "formatted"
                ? dict.humanize.viewFormatted
                : dict.humanize.viewMarkdown}
            </button>
          ))}
        </div>
      </div>

      {view === "formatted" ? (
        <div
          id={id}
          role="region"
          aria-label={dict.humanize.outputLabel}
          className="prose-output min-h-[22rem] w-full overflow-auto rounded-md border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-3 text-sm"
        >
          {loading ? (
            <span className="muted">…</span>
          ) : hasContent ? (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              rehypePlugins={[rehypeSanitize]}
              components={{
                a: ({ children, ...rest }) => (
                  <a {...rest} target="_blank" rel="noopener noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {value}
            </ReactMarkdown>
          ) : null}
        </div>
      ) : (
        <textarea
          id={id}
          value={loading ? "…" : value}
          readOnly
          rows={14}
          className="w-full resize-y rounded-md border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-3 text-sm font-mono"
        />
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onCopyPlain}
          disabled={!hasContent}
          className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {plainCopied ? dict.humanize.copied : dict.humanize.copy}
        </button>
        <button
          type="button"
          onClick={onCopyRich}
          disabled={!hasContent || !richSupported}
          title={!richSupported ? dict.humanize.copyRichUnsupported : undefined}
          className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {richCopied ? dict.humanize.copied : dict.humanize.copyRich}
        </button>
        <button
          type="button"
          onClick={onDownload}
          disabled={!hasContent}
          className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm disabled:opacity-50"
        >
          {dict.humanize.download}
        </button>
      </div>
    </>
  );
}
