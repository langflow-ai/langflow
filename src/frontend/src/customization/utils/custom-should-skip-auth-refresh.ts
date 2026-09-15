import type { AxiosError } from "axios";
import { getBaseUrl } from "./urls";

/**
 * Error codes that mean "authenticated, but this plan does not allow it"
 * rather than "session invalid". The backend sends them on a 403 both as the
 * `X-Langflow-Error-Code` response header and as `detail.error_code`
 * (see `langflow.services.creation_hooks`).
 */
const GATED_ERROR_CODES = new Set([
  "tier_limit_reached",
  "feature_not_in_tier",
]);

function readErrorCode(error: AxiosError): string | undefined {
  const headers = error?.response?.headers as
    | { [key: string]: unknown; get?: (name: string) => unknown }
    | undefined;
  const rawHeader =
    headers?.["x-langflow-error-code"] ??
    headers?.get?.("x-langflow-error-code");
  if (typeof rawHeader === "string" && rawHeader) return rawHeader;

  const detail = (
    error?.response?.data as { detail?: { error_code?: unknown } } | undefined
  )?.detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const code = detail.error_code;
    if (typeof code === "string" && code) return code;
  }
  return undefined;
}

/**
 * Skip the standard 401/403 refresh/logout path for edition-agnostic "gated"
 * 403s. Without this the interceptor renews the token and re-issues the very
 * request that was refused — creating the resource twice if the limit is
 * lifted in between — and logs the user out once the retry budget runs out.
 *
 * Downstream overlays replace this file and may widen the set (e.g. a forced
 * password change); they should keep these codes.
 */
export function customShouldSkipAuthRefresh(error: AxiosError): boolean {
  if (error.response?.status !== 403) return false;
  const code = readErrorCode(error);
  if (code !== undefined && GATED_ERROR_CODES.has(code)) return true;
  if (!error.config?.url) return false;
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
