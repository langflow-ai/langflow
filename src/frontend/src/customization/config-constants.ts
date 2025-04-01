export const BASENAME = "";
export const PORT = 3000;
export const PROXY_TARGET = "http://127.0.0.1:7860";
export const API_ROUTES = ["^/api/v1/", "^/api/v2/", "/health"];
export const BASE_URL_API = `${process.env.ROOT_PATH || ""}/api/v1/`;
export const BASE_URL_API_V2 = `${process.env.ROOT_PATH || ""}/api/v2/`;
export const HEALTH_CHECK_URL = `${process.env.ROOT_PATH || ""}/health_check`;
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
