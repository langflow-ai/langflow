import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

const SUPPORTED_LANGUAGES = [
  "en",
  "de",
  "es",
  "fr",
  "ja",
  "pt",
  "zh-Hans",
] as const;

const normalizeLanguage = (lang?: string | null): string => {
  if (!lang) return "en";

  if (
    SUPPORTED_LANGUAGES.includes(lang as (typeof SUPPORTED_LANGUAGES)[number])
  ) {
    return lang;
  }

  const lowerLang = lang.toLowerCase();

  if (["zh-hans", "zh-cn", "zh-sg"].includes(lowerLang)) {
    return "zh-Hans";
  }

  const baseLang = lang.split("-")[0];

  if (
    SUPPORTED_LANGUAGES.includes(
      baseLang as (typeof SUPPORTED_LANGUAGES)[number],
    )
  ) {
    return baseLang;
  }

  return "en";
};

export const detectedLang = normalizeLanguage(
  localStorage.getItem("languagePreference") || "en",
);

const i18n = i18next.createInstance();

// i18next hardcodes a Locize promotional message via console.info during init.
// Suppress it by temporarily replacing console.info for the synchronous init call.
const _consoleInfo = console.info.bind(console);
console.info = () => {};
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
  },
  lng: detectedLang,
  fallbackLng: "en",
  returnNull: false,
  returnEmptyString: false,
  interpolation: {
    escapeValue: false,
  },
});
console.info = _consoleInfo;

export async function loadLanguage(lang: string): Promise<void> {
  if (lang === "en") return;
  if (i18n.hasResourceBundle(lang, "translation")) return;
  try {
    const messages = await import(`./locales/${lang}.json`);
    i18n.addResourceBundle(lang, "translation", messages.default);
  } catch {
    // Unknown locale — no bundle file exists. i18next's fallbackLng: "en" takes over.
  }
}

export default i18n;
