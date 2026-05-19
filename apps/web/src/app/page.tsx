import { resolveLocale } from "@/lib/locale";
import { getDict } from "@/i18n";
import { Tabs } from "@/components/Tabs";

export default async function HomePage() {
  const locale = await resolveLocale();
  const dict = getDict(locale);
  return <Tabs locale={locale} dict={dict} />;
}
