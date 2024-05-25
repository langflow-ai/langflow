import ReactDOM from "react-dom/client";
import App from "./App";
import ContextWrapper from "./contexts";
import reportWebVitals from "./reportWebVitals";

// @ts-ignore
import "./style/index.css";
// @ts-ignore
import "./style/applies.css";
// @ts-ignore
import axios from "axios";
import { StrictMode } from "react";
import { fetchConfig } from "./controllers/API/utils";
import "./style/classes.css";

async function initialize() {
  try {
    const config = await fetchConfig();
    // Create Axios instance with the fetched timeout configuration
    const timeoutInMilliseconds = config.timeout
      ? config.timeout * 1000
      : 30000;
    axios.defaults.baseURL = "";
    axios.defaults.timeout = timeoutInMilliseconds;
    const root = ReactDOM.createRoot(
      document.getElementById("root") as HTMLElement
    );
    root.render(
      <StrictMode>
        <ContextWrapper>
          <App />
        </ContextWrapper>
      </StrictMode>
    );

    reportWebVitals();
  } catch (error) {
    console.error("Initialization failed:", error);
    // Handle initialization error if necessary
  }
}

// Fetch the configuration and initialize the application
initialize();
