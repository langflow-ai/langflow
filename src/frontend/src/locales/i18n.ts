
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import en from './en.json'
import zh from './zh.json'
import zh_tw from './zh-TW.json'
import { LANGFLOW_DEFAULT_LOCALE } from "../constants/constants";


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
  lng: LANGFLOW_DEFAULT_LOCALE,
  fallbackLng: "en",
  interpolation: {
    escapeValue: false,
  },
});

export default i18n;
