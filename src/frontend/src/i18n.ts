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

export async function loadLanguage(lang: string): Promise<void> {
  if (lang === "en") return;
  if (i18n.hasResourceBundle(lang, "translation")) return;
  const messages = await import(`./locales/${lang}.json`);
  i18n.addResourceBundle(lang, "translation", messages.default);
}

export default i18n;
