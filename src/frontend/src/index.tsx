import ReactDOM from "react-dom/client";
import App from "./App";
import ContextWrapper from "./contexts";
import reportWebVitals from "./reportWebVitals";

// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./style/applies.css";
// @ts-ignore
import "./style/classes.css";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);
root.render(
  <ContextWrapper>
    <App />
  </ContextWrapper>,
);
reportWebVitals();
