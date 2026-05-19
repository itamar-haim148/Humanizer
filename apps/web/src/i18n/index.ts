import en from "./en.json";
import he from "./he.json";

export type Locale = "en" | "he";

export type Dict = typeof en;

const DICTS: Record<Locale, Dict> = { en, he } as const;

export function getDict(locale: Locale): Dict {
  return DICTS[locale] ?? en;
}

export function formatString(
  template: string,
  vars: Record<string, string | number>,
): string {
  return template.replace(/\{(\w+)\}/g, (_, key) =>
    key in vars ? String(vars[key]) : `{${key}}`,
  );
}
