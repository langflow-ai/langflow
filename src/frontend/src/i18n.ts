import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import {
  AUTO_LANGUAGE,
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
  fr: async () => (await import("./locales/fr.json")).default,
  es: async () => (await import("./locales/es.json")).default,
  de: async () => (await import("./locales/de.json")).default,
  pt: async () => (await import("./locales/pt.json")).default,
  ja: async () => (await import("./locales/ja.json")).default,
  "zh-Hans": async () => (await import("./locales/zh-Hans.json")).default,
  ru: async () => (await import("./locales/ru.json")).default,
  ko: async () => (await import("./locales/ko.json")).default,
};

// i18next 在初始化期间会通过 console.info 输出 Locize 推广信息。
// i18next emits a Locize promotional message through console.info during init.
// 临时替换 console.info，以便在同步初始化调用期间静默该信息。
// Temporarily replace console.info to silence that message during the synchronous init call.
const i18n = i18next.createInstance();
const _consoleInfo = console.info.bind(console);
console.info = () => {};
i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
  },
  lng: "en",
  fallbackLng: "en",
  returnNull: false,
  returnEmptyString: false,
  interpolation: {
    escapeValue: false,
  },
});
console.info = _consoleInfo;

/**
 * 将浏览器或已存储的语言值规范化为支持的区域设置。
 * Normalizes a browser or stored language value into a supported locale.
 *
 * @param lang - 来自本地存储或浏览器的原始语言值。 / Raw language value from local storage or the browser.
 * @returns 支持的语言代码；无法解析时返回英语。 / A supported language code, or English when the value cannot be resolved.
 */
export function normalizeLanguage(lang?: string | null): SupportedLanguage {
  const rawLanguage = lang?.trim();

  if (!rawLanguage || rawLanguage === AUTO_LANGUAGE) {
    return "en";
  }

  const language = rawLanguage.toLowerCase();

  switch (true) {
    case language.startsWith("zh-hant") ||
      language === "zh-tw" ||
      language.startsWith("zh-tw-") ||
      language === "zh-hk" ||
      language.startsWith("zh-hk-") ||
      language === "zh-mo" ||
      language.startsWith("zh-mo-"):
      return "en";
    case language.startsWith("zh"):
      return "zh-Hans";
    case language.startsWith("ko"):
      return "ko";
    case language.startsWith("ru"):
      return "ru";
    default:
      break;
  }

  const exactLanguage = SUPPORTED_LANGUAGES.find(
    (supportedLanguage) => supportedLanguage.code.toLowerCase() === language,
  );

  if (exactLanguage) {
    return exactLanguage.code;
  }

  const baseLanguage = language.split("-")[0];
  const baseMatch = SUPPORTED_LANGUAGES.find(
    (supportedLanguage) =>
      supportedLanguage.code.toLowerCase() === baseLanguage,
  );

  return baseMatch?.code ?? "en";
}

/**
 * 读取浏览器首选语言并规范化为支持的区域设置。
 * Reads the browser-preferred language and normalizes it into a supported locale.
 *
 * @returns 支持的浏览器语言；无可用浏览器语言时返回英语。 / A supported browser language, or English when no browser language is available.
 */
export function getBrowserLanguage(): SupportedLanguage {
  return normalizeLanguage(
    typeof navigator === "undefined" ? undefined : navigator.language,
  );
}

/**
 * 加载并切换 i18n 到请求的受支持语言。
 * Loads and switches i18n to the requested supported language.
 *
 * @param lang - 要加载的原始语言值。 / Raw language value to load.
 * @returns 已应用的受支持语言代码。 / The supported language code that was applied.
 */
export async function loadLanguage(
  lang?: string | null,
): Promise<SupportedLanguage> {
  const normalizedLanguage = normalizeLanguage(lang);

  if (!i18n.hasResourceBundle(normalizedLanguage, "translation")) {
    const messages = await LANGUAGE_LOADERS[normalizedLanguage]();
    i18n.addResourceBundle(normalizedLanguage, "translation", messages);
  }

  await i18n.changeLanguage(normalizedLanguage);
  return normalizedLanguage;
}

export default i18n;
