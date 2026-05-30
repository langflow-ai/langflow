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

const LANG_FILE_MAP: Record<string, string> = {
  en: "en",
  "en-US": "en",
  "en-GB": "en",
  de: "de",
  "de-DE": "de",
  es: "es",
  "es-ES": "es",
  fr: "fr",
  "fr-FR": "fr",
  ja: "ja",
  "ja-JP": "ja",
  pt: "pt",
  "pt-BR": "pt",
  zh: "zh-Hans",
  "zh-CN": "zh-Hans",
  "zh-TW": "zh-Hans",
  "zh-HK": "zh-Hans",
  "zh-SG": "zh-Hans",
  "zh-Hans": "zh-Hans",
};

export async function loadLanguage(lang: string): Promise<void> {
  const file = LANG_FILE_MAP[lang] ?? LANG_FILE_MAP[lang.split("-")[0]] ?? "en";
  console.log(`file ${file}`);
  if (file === "en") return;
  if (i18n.hasResourceBundle(file, "translation")) return;
  console.log(`import language ${file}`)
  const messages = await import(`./locales/${file}.json`);
  i18n.addResourceBundle(file, "translation", messages.default);
  i18n.changeLanguage(file);
}

export default i18n;
