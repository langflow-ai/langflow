import { BASE_URL_API, BASE_URL_API_V2 } from "../../../constants/constants";

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
  FOLDERS: `projects`,
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

// IMPORTANT: FOLDERS endpoint now points to 'projects' for backward compatibility

export function getURL(
  key: keyof typeof URLs,
  params: any = {},
  v2: boolean = false,
) {
  let url = URLs[key];
  Object.keys(params).forEach((key) => (url += `/${params[key]}`));
  return `${v2 ? BASE_URL_API_V2 : BASE_URL_API}${url.toString()}`;
}

export type URLsType = typeof URLs;
