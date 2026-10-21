import {
  BASE_URL_API,
  BASENAME,
  HEALTH_CHECK_URL,
} from "@/customization/config-constants";

export function getBaseUrl(): string {
  return BASE_URL_API || "/api/v1/";
}

// Backend-provided stream paths are root-relative; keep them under the prefix.
export function applyBasePath(url: string): string {
  if (!BASENAME || !url.startsWith("/") || url.startsWith("//")) {
    return url;
  }
  if (url === BASENAME || url.startsWith(`${BASENAME}/`)) {
    return url;
  }
  return `${BASENAME}${url}`;
}

export function getHealthCheckUrl(): string {
  return HEALTH_CHECK_URL || "/health";
}

export const LangflowButtonRedirectTarget = () => {
  return "https://langflow.org";
};
