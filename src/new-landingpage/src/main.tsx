import React from "react";
import ReactDOM from "react-dom/client";
import { ClerkProvider } from "@clerk/clerk-react";
import { CookiesProvider } from "react-cookie";
import App from "./App";
import "./index.css";

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";

if (!clerkPublishableKey) {
  console.warn("VITE_CLERK_PUBLISHABLE_KEY is not set. Clerk login will not function correctly.");
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <CookiesProvider>
      <ClerkProvider publishableKey={clerkPublishableKey}>
        <App />
      </ClerkProvider>
    </CookiesProvider>
  </React.StrictMode>,
);