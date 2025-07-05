import ReactDOM from "react-dom/client";
import reportWebVitals from "./reportWebVitals";

import "./style/classes.css";
import "./style/index.css";
import "./App.css";

import App from "./customization/custom-App";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(<App />);
reportWebVitals();
