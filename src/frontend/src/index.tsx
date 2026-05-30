import "./i18n";
import ReactDOM from "react-dom/client";
import { loadLanguage } from "./i18n";
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
  localStorage.getItem("languagePreference") || navigator.language || "en";

loadLanguage(detectedLang).then(() => {
  const root = ReactDOM.createRoot(
    document.getElementById("root") as HTMLElement,
  );
  root.render(<App />);
  reportWebVitals();
});
