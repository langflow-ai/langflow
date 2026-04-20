import i18n, { loadLanguage, resolveLanguage } from "./i18n";
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

const detectedLang = resolveLanguage(
  localStorage.getItem("languagePreference") || navigator.language || "en",
);

const renderApp = () => {
  const root = ReactDOM.createRoot(
    document.getElementById("root") as HTMLElement,
  );
  root.render(<App />);
  reportWebVitals();
};

const initializeApp = async () => {
  try {
    await loadLanguage(detectedLang);
    await i18n.changeLanguage(detectedLang);
  } catch {
    await i18n.changeLanguage("en");
  }

  renderApp();
};

void initializeApp();
