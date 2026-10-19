declare const __LANGFLOW_BASE_PATH__: string;

// Node tooling also imports this module, without Vite's build definitions.
export const BASENAME =
  typeof __LANGFLOW_BASE_PATH__ === "undefined" ? "" : __LANGFLOW_BASE_PATH__;
export const PORT = 3000;
export const PROXY_TARGET = "http://localhost:7860";
export const API_ROUTES = ["^/api/v1/", "^/api/v2/", "/health"];
export const BASE_URL_API = `${BASENAME}/api/v1/`;
export const BASE_URL_API_V2 = `${BASENAME}/api/v2/`;
export const HEALTH_CHECK_URL = `${BASENAME}/health_check`;
export const DOCS_LINK = "https://docs.langflow.org";

export default {
  DOCS_LINK,
  BASENAME,
  PORT,
  PROXY_TARGET,
  API_ROUTES,
  BASE_URL_API,
  BASE_URL_API_V2,
  HEALTH_CHECK_URL,
};
