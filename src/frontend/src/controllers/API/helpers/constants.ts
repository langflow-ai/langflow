import { BASE_URL_API } from "../../../constants/constants";

export const URLs = {
  TRANSACTIONS: `monitor/transactions`,
  API_KEY: `api_key`,
  FILES: `files`,
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
  FOLDERS: `folders`,
  VARIABLES: `variables`,
  VALIDATE: `validate`,
  CONFIG: `config`,
  STARTER_PROJECTS: `starter-projects`,
  SIDEBAR_CATEGORIES: `sidebar_categories`,
  ALL: `all`,
} as const;

export function getURL(key: keyof typeof URLs, params: any = {}) {
  let url = URLs[key];
  Object.keys(params).forEach((key) => (url += `/${params[key]}`));
  return `${BASE_URL_API}${url.toString()}`;
}

export type URLsType = typeof URLs;
