export const BASENAME = "";
export const PORT = 3000;
export const PROXY_TARGET = "http://localhost:7860";
export const API_ROUTES = ["^/api/v1/", "^/api/v2/", "/health"];
export const BASE_URL_API = "/api/v1/";
export const BASE_URL_API_V2 = "/api/v2/";
export const HEALTH_CHECK_URL = "/health_check";
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
