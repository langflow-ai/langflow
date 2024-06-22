
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from './en.json'
import zh from './zh.json'
import zh_tw from './zh-TW.json'

const resources = {
  en: {
    translation: en
  },
  zh: {
    translation: zh
  },
  "zh-TW": {
    translation: zh_tw
  }
}

i18n.use(initReactI18next).init({
  resources,
  lng: "zh-TW",
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
