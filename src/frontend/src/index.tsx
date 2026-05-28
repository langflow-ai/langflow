import i18n, { loadLanguage, normalizeLanguage } from "./i18n";
import ReactDOM from "react-dom/client";
import reportWebVitals from "./reportWebVitals";

import "./style/classes.css";
// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./App.css";
import "./style/applies.css";

// @ts-ignore
import App from "./customization/custom-App";

const detectedLang =
  localStorage.getItem("languagePreference") ||
  navigator.language.split("-")[0] ||
  "en";

const startupLanguage = normalizeLanguage(detectedLang);

loadLanguage(startupLanguage).then(async () => {
  await i18n.changeLanguage(startupLanguage);
  const root = ReactDOM.createRoot(
    document.getElementById("root") as HTMLElement,
  );
  root.render(<App />);
  reportWebVitals();
});
