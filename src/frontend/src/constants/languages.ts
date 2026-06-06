export const AUTO_LANGUAGE = "auto";
export const LANGUAGE_PREFERENCE_STORAGE_KEY = "languagePreference";

export const SUPPORTED_LANGUAGES = [
  { code: "de", label: "Deutsch" },
  { code: "en", label: "English" },
  { code: "es", label: "Español" },
  { code: "fr", label: "Français" },
  { code: "ja", label: "日本語" },
  { code: "ko", label: "한국어" },
  { code: "pt", label: "Português" },
  { code: "ru", label: "Русский" },
  { code: "zh-Hans", label: "中文" },
] as const;

export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number]["code"];
export type LanguagePreference = SupportedLanguage | typeof AUTO_LANGUAGE;
