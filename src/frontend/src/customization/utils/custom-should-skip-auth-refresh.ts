import type { AxiosError } from "axios";

/**
 * OSS no-op: never skip the standard 401/403 refresh/logout path.
 * Downstream overlays can return true for edition-specific 403s that mean
 * "authenticated but gated" rather than "session invalid" — e.g. a forced
 * password change — so the interceptor does not log the user out.
 */
export function customShouldSkipAuthRefresh(_error: AxiosError): boolean {
  return false;
}
