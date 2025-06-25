// Environment config strictly for frontend
export const CLERK_AUTH_ENABLED =
  import.meta.env.VITE_CLERK_AUTH_ENABLED === "true";
export const CLERK_PUBLISHABLE_KEY =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || "";

// API base URLs
export const BASE_URL_API = "/api/v1/";
export const BASE_URL_API_V2 = "/api/v2/";

// All backend API endpoints
export const URLs = {
  TRANSACTIONS: `monitor/transactions`,
  API_KEY: `api_key`,
  FILES: `files`,
  FILE_MANAGEMENT: `files`,
  VERSION: `version`,
  MESSAGES: `monitor/messages`,
  BUILDS: `monitor/builds`,
  STORE: `store`,
  USERS: "users",
  LOGOUT: `logout`,
  LOGIN: `login`,
  AUTOLOGIN: "auto_login",
  REFRESH: "refresh",
  BUILD: `build`,
  CUSTOM_COMPONENT: `custom_component`,
  FLOWS: `flows`,
  FOLDERS: `projects`, // alias for backward compatibility
  PROJECTS: `projects`,
  VARIABLES: `variables`,
  VALIDATE: `validate`,
  CONFIG: `config`,
  STARTER_PROJECTS: `starter-projects`,
  SIDEBAR_CATEGORIES: `sidebar_categories`,
  ALL: `all`,
  VOICE: `voice`,
  PUBLIC_FLOW: `flows/public_flow`,
  MCP: `mcp/project`,
  MCP_SERVERS: `mcp/servers`,
} as const;

// URL constructor
export function getURL(
  key: keyof typeof URLs,
  params: any = {},
  v2: boolean = false,
): string {
  if (CLERK_AUTH_ENABLED && (key === "LOGIN" || key === "REFRESH")) {
    throw new Error(
      `Legacy endpoint "${key}" is disabled under Clerk authentication`,
    );
  }

  let url = URLs[key];
  Object.keys(params).forEach((key) => {
    url += `/${params[key]}`;
  });

  return `${v2 ? BASE_URL_API_V2 : BASE_URL_API}${url}`;
}

export type URLsType = typeof URLs;
