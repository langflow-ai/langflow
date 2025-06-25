import React from "react";
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

import { ClerkProvider } from "@clerk/clerk-react";

// Load Clerk publishable key from Vite env
const clerkFrontendApi = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

const root = ReactDOM.createRoot(
  document.getElementById("root") as HTMLElement,
);

root.render(
  <React.StrictMode>
    <ClerkProvider
      publishableKey={clerkFrontendApi}
      afterSignInUrl="/flows"
      afterSignUpUrl="/flows"
    >
      <App />
    </ClerkProvider>
  </React.StrictMode>,
);

reportWebVitals();
