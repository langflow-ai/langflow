import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

const detectedLang =
  localStorage.getItem("languagePreference") ||
  navigator.language.split("-")[0] ||
  "en";

// i18next hardcodes a Locize promotional message via console.info during init.
// Suppress it by temporarily replacing console.info for the synchronous init call.
const _consoleInfo = console.info.bind(console);
console.info = () => {};
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
console.info = _consoleInfo;

export async function loadLanguage(lang: string): Promise<void> {
  if (lang !== "en" && !i18n.hasResourceBundle(lang, "translation")) {
    try {
      const messages = await import(`./locales/${lang}.json`);
      i18n.addResourceBundle(lang, "translation", messages.default);
    } catch {
      // Unknown locale — no bundle file exists. i18next's fallbackLng: "en" takes over.
      return;
    }
  }
  i18n.changeLanguage(lang);
}

export default i18n;
