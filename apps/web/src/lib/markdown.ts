/**
 * Clipboard-oriented Markdown helpers.
 *
 * On-screen rendering uses `react-markdown` (React-tree, no string-HTML
 * mounting) — see `components/FormattedOutput.tsx`.
 *
 * The clipboard, however, accepts HTML as a byte payload: that's how
 * Google Docs, Word, and Notion pick up rich formatting on paste. We
 * generate that payload with `marked`. The HTML is handed to the OS via
 * `navigator.clipboard.write([new ClipboardItem(...)])`; it is never
 * mounted into the live DOM of this app, so React's XSS surface is not
 * involved here.
 */

import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: false });

/**
 * Copy both a rich HTML representation and the plain Markdown source
 * to the clipboard. HTML-aware paste targets pick up the formatted
 * version; plain-text targets get the Markdown.
 *
 * Returns true on success, false if the Clipboard API is unavailable.
 */
export async function copyFormatted(markdown: string): Promise<boolean> {
  if (typeof navigator === "undefined" || !navigator.clipboard) return false;
  const fragment = marked.parse(markdown, { async: false }) as string;
  const htmlDoc = `<!doctype html><meta charset="utf-8">${fragment}`;

  try {
    if (typeof ClipboardItem !== "undefined" && navigator.clipboard.write) {
      const item = new ClipboardItem({
        "text/html": new Blob([htmlDoc], { type: "text/html" }),
        "text/plain": new Blob([markdown], { type: "text/plain" }),
      });
      await navigator.clipboard.write([item]);
      return true;
    }
    await navigator.clipboard.writeText(markdown);
    return true;
  } catch {
    try {
      await navigator.clipboard.writeText(markdown);
      return true;
    } catch {
      return false;
    }
  }
}
