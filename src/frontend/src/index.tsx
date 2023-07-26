import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import ContextWrapper from "./contexts";
import reportWebVitals from "./reportWebVitals";

import { ApiInterceptor } from "./controllers/API/api";
import "./style/index.css";
import "./style/classes.css";
import "./style/applies.css";

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement
);
root.render(
  <ContextWrapper>
    <BrowserRouter>
      <App />
      <ApiInterceptor />
    </BrowserRouter>
  </ContextWrapper>
);
reportWebVitals();
