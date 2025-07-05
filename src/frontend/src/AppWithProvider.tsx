import React from "react";
import App from "./customization/custom-App";
import ClerkAuthProvider from "./clerk/clerk-provider";
import { IS_CLERK_AUTH } from "./constants/clerk";

const AppWithProvider = () => (
  IS_CLERK_AUTH ? (
    <ClerkAuthProvider>
      <App />
    </ClerkAuthProvider>
  ) : (
    <App />
  )
);

export default AppWithProvider;
