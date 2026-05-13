import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

const supportedLanguages = ["en", "th"];
const localeModules = import.meta.glob("./locales/*.json");

function normalizeLanguage(lang: string | null | undefined): string {
  if (!lang) return "en";
  return lang.split("-")[0].toLowerCase();
}

function getInitialLanguage(): string {
  const saved = localStorage.getItem("languagePreference");
  if (saved && supportedLanguages.includes(saved)) return saved;

  const browserLanguages = navigator.languages?.length
    ? navigator.languages
    : [navigator.language];

  for (const locale of browserLanguages) {
    const normalized = normalizeLanguage(locale);
    if (supportedLanguages.includes(normalized)) return normalized;
  }

  return "en";
}

i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
  },
  lng: getInitialLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export async function loadLanguage(lang: string): Promise<void> {
  const normalized = normalizeLanguage(lang);
  if (!supportedLanguages.includes(normalized)) return;
  if (i18n.hasResourceBundle(normalized, "translation")) return;

  const loader = localeModules[`./locales/${normalized}.json`];
  if (!loader) return;

  const messages = await loader();
  i18n.addResourceBundle(
    normalized,
    "translation",
    (messages as { default: Record<string, string> }).default,
  );
}

export default i18n;
