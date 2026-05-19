import type { Metadata } from "next";
import { Inter, Heebo } from "next/font/google";
import { resolveLocale, resolveTheme } from "@/lib/locale";
import { getDict } from "@/i18n";
import { Header } from "@/components/Header";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

const heebo = Heebo({
  subsets: ["hebrew", "latin"],
  display: "swap",
  variable: "--font-heebo",
});

export const metadata: Metadata = {
  title: "Humanize AI",
  description:
    "Free, no-signup AI text humanizer and AI detector. English + Hebrew.",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await resolveLocale();
  const theme = await resolveTheme();
  const dict = getDict(locale);
  const dir = locale === "he" ? "rtl" : "ltr";

  return (
    <html
      lang={locale}
      dir={dir}
      className={`${inter.variable} ${heebo.variable} ${theme === "dark" ? "dark" : ""}`}
    >
      <body className="min-h-screen antialiased">
        <Header locale={locale} theme={theme} dict={dict} />
        <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
          {children}
        </main>
      </body>
    </html>
  );
}
