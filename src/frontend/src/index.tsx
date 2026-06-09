import "./i18n";
import ReactDOM from "react-dom/client";
import {
  AUTO_LANGUAGE,
  LANGUAGE_PREFERENCE_STORAGE_KEY,
} from "./constants/languages";
import { getBrowserLanguage, loadLanguage } from "./i18n";
import reportWebVitals from "./reportWebVitals";
import { getLocalStorage } from "./utils/local-storage-util";

import "./style/classes.css";
// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./App.css";
import "./style/applies.css";

// @ts-ignore
import App from "./customization/custom-App";

const languagePreference = getLocalStorage(LANGUAGE_PREFERENCE_STORAGE_KEY);
const detectedLang =
  languagePreference && languagePreference !== AUTO_LANGUAGE
    ? languagePreference
    : getBrowserLanguage();

loadLanguage(detectedLang).then(() => {
  const root = ReactDOM.createRoot(
    document.getElementById("root") as HTMLElement,
  );
  root.render(<App />);
  reportWebVitals();
});
