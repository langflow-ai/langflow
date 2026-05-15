import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

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

const languageAliases: Record<string, string> = {
  zh: "zh-Hans",
  "zh-CN": "zh-Hans",
  "zh-TW": "zh-Hans",
};

function resolveLanguage(lang: string): string {
  return languageAliases[lang] ?? lang;
}

export async function loadLanguage(lang: string): Promise<void> {
  const resolved = resolveLanguage(lang);
  if (resolved === "en") return;
  if (i18n.hasResourceBundle(resolved, "translation")) return;
  try {
    const messages = await import(`./locales/${resolved}.json`);
    i18n.addResourceBundle(resolved, "translation", messages.default);
  } catch {
    // Locale file missing — i18next fallbackLng "en" keeps the app usable.
  }
}

export default i18n;
