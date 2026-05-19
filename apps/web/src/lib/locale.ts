import { cookies, headers } from "next/headers";
import type { Locale } from "@/i18n";

const LANG_COOKIE = "lang";
const THEME_COOKIE = "theme";

function pickFromAcceptLanguage(value: string | null): Locale {
  if (!value) return "en";
  const first = value.split(",")[0]?.trim().toLowerCase() ?? "";
  if (first.startsWith("he")) return "he";
  return "en";
}

export async function resolveLocale(): Promise<Locale> {
  const c = await cookies();
  const cookieValue = c.get(LANG_COOKIE)?.value;
  if (cookieValue === "he" || cookieValue === "en") return cookieValue;
  const h = await headers();
  return pickFromAcceptLanguage(h.get("accept-language"));
}

export type Theme = "light" | "dark";

export async function resolveTheme(): Promise<Theme> {
  const c = await cookies();
  const v = c.get(THEME_COOKIE)?.value;
  return v === "dark" ? "dark" : "light";
}

export const COOKIE_KEYS = {
  language: LANG_COOKIE,
  theme: THEME_COOKIE,
} as const;
