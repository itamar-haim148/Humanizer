"use client";

import type { Dict, Locale } from "@/i18n";
import type { Theme } from "@/lib/locale";

const ONE_YEAR = 60 * 60 * 24 * 365;

function setCookie(name: string, value: string): void {
  document.cookie = `${name}=${value}; path=/; max-age=${ONE_YEAR}; SameSite=Lax`;
}

interface HeaderProps {
  locale: Locale;
  theme: Theme;
  dict: Dict;
}

export function Header({ locale, theme, dict }: HeaderProps) {
  function toggleLanguage(): void {
    const next: Locale = locale === "he" ? "en" : "he";
    setCookie("lang", next);
    window.location.reload();
  }

  function toggleTheme(): void {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setCookie("theme", next);
    window.location.reload();
  }

  const themeLabel =
    theme === "dark"
      ? dict.app.themeToggle.toLight
      : dict.app.themeToggle.toDark;

  return (
    <header className="border-b border-[rgb(var(--border))]">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6 lg:px-8">
        <div>
          <h1 className="text-xl font-bold tracking-tight sm:text-2xl">
            {dict.app.title}
          </h1>
          <p className="muted text-sm">{dict.app.subtitle}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleLanguage}
            className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--surface))]"
          >
            {dict.app.languageToggle}
          </button>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={themeLabel}
            title={themeLabel}
            className="rounded-md border border-[rgb(var(--border))] px-3 py-1.5 text-sm hover:bg-[rgb(var(--surface))]"
          >
            {theme === "dark" ? "☀" : "☾"}
          </button>
        </div>
      </div>
    </header>
  );
}
