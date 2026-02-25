import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import zhCN from "./locales/zh-CN/translation.json";
import en from "./locales/en/translation.json";

const savedLang = localStorage.getItem("langflow-lang") || "zh-CN";

i18n.use(initReactI18next).init({
  resources: {
    "zh-CN": { translation: zhCN },
    en: { translation: en },
  },
  lng: savedLang,
  fallbackLng: "en",
  interpolation: {
    // React 已做 XSS 防护，无需转义
    escapeValue: false,
  },
});

export default i18n;
