import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";
import de from "./locales/de.json";
import es from "./locales/es.json";
import fr from "./locales/fr.json";
import ja from "./locales/ja.json";
import pt from "./locales/pt.json";
import zhHans from "./locales/zh-Hans.json";

const localeResources = {
  en,
  fr,
  es,
  de,
  pt,
  ja,
  "zh-Hans": zhHans,
} as const;

type SupportedLanguage = keyof typeof localeResources;

export function normalizeLanguage(lang: string): SupportedLanguage {
  const trimmed = lang.trim();

  if (!trimmed) {
    return "en";
  }

  const lower = trimmed.toLowerCase();

  if (lower.startsWith("zh")) {
    return "zh-Hans";
  }

  const supportedLanguage = (
    Object.keys(localeResources) as SupportedLanguage[]
  ).find((language) => language.toLowerCase() === lower);

  return supportedLanguage ?? "en";
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
  },
  lng: "en",
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export async function loadLanguage(lang: string): Promise<void> {
  const resolvedLanguage = normalizeLanguage(lang);

  if (
    resolvedLanguage !== "en" &&
    !i18n.hasResourceBundle(resolvedLanguage, "translation")
  ) {
    const messages = localeResources[resolvedLanguage];
    i18n.addResourceBundle(
      resolvedLanguage,
      "translation",
      messages,
      true,
      true,
    );

    if (!i18n.hasResourceBundle(resolvedLanguage, "translation")) {
      i18n.store.data[resolvedLanguage] ??= {};
      i18n.store.data[resolvedLanguage].translation = messages;
    }
  }
}

export default i18n;
