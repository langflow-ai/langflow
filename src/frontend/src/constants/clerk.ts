export const IS_CLERK_AUTH =
  String(process.env.CLERK_AUTH_ENABLED).toLowerCase() === "true";
export const CLERK_PUBLISHABLE_KEY = process.env.CLERK_PUBLISHABLE_KEY || "";
