import type { AxiosError } from "axios";
import { getBaseUrl } from "./urls";

/**
 * Collaboration 403s are authorization denials for an authenticated caller.
 * Refreshing the session must not replay a denied edit or share mutation.
 * Authentication failures (401) retain the standard refresh/logout path.
 */
export function customShouldSkipAuthRefresh(error: AxiosError): boolean {
  if (error.response?.status !== 403 || !error.config?.url) return false;
  const requestUrl = new URL(error.config.url, window.location.origin);
  return ["flows", "projects", "authz"].some((resource) => {
    const endpoint = new URL(
      `${getBaseUrl()}${resource}`,
      window.location.origin,
    );
    return (
      requestUrl.origin === endpoint.origin &&
      (requestUrl.pathname === endpoint.pathname ||
        requestUrl.pathname.startsWith(`${endpoint.pathname}/`))
    );
  });
}
