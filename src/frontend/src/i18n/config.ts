
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import translationEN from './en.json'
import translationZH from './zh.json'
import translationZHTW from './zh-TW.json'

const resources = {
  en: {
    translation: translationEN
  },
  zh: {
    translation: translationZH
  },
  'zh-TW': {
    translation: translationZHTW
  }
}

i18n.use(initReactI18next).init({
  resources,
  lng: "zh",
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
