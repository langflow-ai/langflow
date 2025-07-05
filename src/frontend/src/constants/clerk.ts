export const IS_CLERK_AUTH =
  String(process.env.CLERK_AUTH_ENABLED).toLowerCase() === "true";
export const CLERK_PUBLISHABLE_KEY = process.env.CLERK_PUBLISHABLE_KEY || "";

// Dummy password used when registering Clerk users in the backend
export const CLERK_DUMMY_PASSWORD = "clerk_dummy_password";
