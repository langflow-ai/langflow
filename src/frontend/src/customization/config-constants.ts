import { normalizeBasePath } from "./base-path";

// The backend sets the base element before any frontend modules execute.
const documentBase =
  typeof document === "undefined"
    ? undefined
    : document.querySelector("base")?.getAttribute("href");
export const BASENAME = documentBase?.startsWith("/")
  ? normalizeBasePath(documentBase)
  : "";
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
