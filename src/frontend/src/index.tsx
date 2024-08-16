import ReactDOM from "react-dom/client";
import ContextWrapper from "./contexts";
import reportWebVitals from "./reportWebVitals";

import "./style/classes.css";
// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./App.css";
import "./style/applies.css";

// @ts-ignore
import App from "./App";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(
  <ContextWrapper>
    <App />
  </ContextWrapper>,
);
reportWebVitals();
