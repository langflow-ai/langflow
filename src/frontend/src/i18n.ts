import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import {
  SUPPORTED_LANGUAGES,
  type SupportedLanguage,
} from "./constants/languages";
import en from "./locales/en.json";

type LocaleMessages = Record<string, string>;

const LANGUAGE_LOADERS: Record<
  SupportedLanguage,
  () => Promise<LocaleMessages>
> = {
  en: async () => en,
  de: async () => (await import("./locales/de.json")).default,
  es: async () => (await import("./locales/es.json")).default,
  fr: async () => (await import("./locales/fr.json")).default,
  ja: async () => (await import("./locales/ja.json")).default,
  ko: async () => (await import("./locales/ko.json")).default,
  pt: async () => (await import("./locales/pt.json")).default,
  ru: async () => (await import("./locales/ru.json")).default,
  "zh-Hans": async () => (await import("./locales/zh-Hans.json")).default,
};

export const normalizeLanguage = (lang?: string | null): SupportedLanguage => {
  if (!lang) return "en";

  const exactLanguage = SUPPORTED_LANGUAGES.find(
    (supportedLanguage) => supportedLanguage.code === lang,
  );

  if (exactLanguage) {
    return exactLanguage.code;
  }

  const lowerLang = lang.toLowerCase();

  if (["zh-hans", "zh-cn", "zh-sg"].includes(lowerLang)) {
    return "zh-Hans";
  }

  const baseLang = lang.split("-")[0];
  const baseMatch = SUPPORTED_LANGUAGES.find(
    (supportedLanguage) => supportedLanguage.code === baseLang,
  );

  return baseMatch?.code ?? "en";
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

export async function loadLanguage(lang: string): Promise<SupportedLanguage> {
  const normalizedLanguage = normalizeLanguage(lang);

  if (normalizedLanguage === "en") return normalizedLanguage;
  if (i18n.hasResourceBundle(normalizedLanguage, "translation")) {
    return normalizedLanguage;
  }

  const messages = await LANGUAGE_LOADERS[normalizedLanguage]();
  i18n.addResourceBundle(normalizedLanguage, "translation", messages);
  return normalizedLanguage;
}

export default i18n;
