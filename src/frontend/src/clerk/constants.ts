// src/clerk/constants.ts
export const IS_CLERK_AUTH =
  String(import.meta.env.VITE_CLERK_AUTH_ENABLED).toLowerCase() === "true";

export const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";
export const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";
