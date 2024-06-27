
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import translationEN from './en.json'
import translationZH from './zh.json'

const resources = {
  en: {
    translation: translationEN
  },
  zh: {
    translation: translationZH
  }
}

function getDefaultLanguage() {
  return navigator.language.includes("zh") ? "zh" : "en";
}

i18n.use(initReactI18next).init({
  resources,
  lng: getDefaultLanguage(),
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
