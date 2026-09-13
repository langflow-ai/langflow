/**
 * Shape produced by FastAPI validation errors and generic axios responses.
 * Kept internal — callers receive plain strings.
 */
type ApiDetailEntry =
  | { msg?: string; message?: string; code?: string }
  | string;

type ApiErrorShape = {
  response?: { data?: { detail?: ApiDetailEntry[] | ApiDetailEntry } };
  message?: string;
};

/**
 * Extracts one or more human-readable messages from an unknown API error.
 *
 * Handles three FastAPI / axios error shapes in priority order:
 *   1. `response.data.detail` — array of `{ msg }` objects (validation errors)
 *   2. `response.data.detail` — plain string
 *   3. `error.message`        — axios / native Error message
 *
 * Always returns at least one element so callers can spread directly into
 * `setErrorData({ list: extractApiErrorMessages(error) })`.
 */
export function extractApiErrorMessages(error: unknown): string[] {
  if (!error || typeof error !== "object") {
    return ["An unknown error occurred"];
  }

  const e = error as ApiErrorShape;
  const detail = e.response?.data?.detail;

  if (Array.isArray(detail)) {
    const msgs = detail
      .map((entry) => {
        if (typeof entry === "string") return entry;
        if (entry && typeof entry === "object") {
          const msg = (entry as { msg?: string }).msg;
          return typeof msg === "string" ? msg : JSON.stringify(entry);
        }
        return String(entry);
      })
      .filter(Boolean);
    if (msgs.length > 0) return msgs;
  }

  if (typeof detail === "string" && detail) return [detail];
  if (detail && typeof detail === "object") {
    const structured = detail as { message?: string; msg?: string };
    if (typeof structured.message === "string" && structured.message) {
      return [structured.message];
    }
    if (typeof structured.msg === "string" && structured.msg) {
      return [structured.msg];
    }
  }
  if (typeof e.message === "string" && e.message) return [e.message];
  return ["An unknown error occurred"];
}

/** Return the stable backend code without exposing response internals to UI components. */
export function extractApiErrorCode(error: unknown): string | undefined {
  if (!error || typeof error !== "object") return undefined;
  const detail = (error as ApiErrorShape).response?.data?.detail;
  if (detail && !Array.isArray(detail) && typeof detail === "object") {
    return typeof detail.code === "string" ? detail.code : undefined;
  }
  return undefined;
}
