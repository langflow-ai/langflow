import ReactDOM from "react-dom/client";
import i18n, { loadLanguage } from "./i18n";
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

function renderApp() {
  const root = ReactDOM.createRoot(
    document.getElementById("root") as HTMLElement,
  );
  root.render(<App />);
  reportWebVitals();
}

loadLanguage(detectedLang)
  .catch((err) => {
    console.warn(
      `Failed to load language "${detectedLang}", falling back to English.`,
      err,
    );
  })
  .then(() => {
    i18n.changeLanguage(detectedLang);
    renderApp();
  });
