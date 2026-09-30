import axios from "axios";

/**
 * Extract a string from the `detail` field of an Axios error response.
 *
 * FastAPI returns `detail` as a plain string for most HTTP errors, but
 * Pydantic validation errors (422) return an array of objects with a `msg`
 * property.  This helper handles both shapes.
 */
function extractDetail(data: unknown): string | undefined {
  if (data == null || typeof data !== "object") return undefined;

  const detail = (data as Record<string, unknown>).detail;

  if (typeof detail === "string") return detail;

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry: unknown) => {
        if (typeof entry === "string") return entry;
        if (entry != null && typeof entry === "object") {
          const msg = (entry as Record<string, unknown>).msg;
          if (typeof msg === "string") return msg;
        }
        return String(entry);
      })
      .join("; ");
  }

  return undefined;
}

/**
 * Extracts a user-friendly error message from an unknown catch value.
 * Prefers `response.data.detail` for Axios errors, then `.message`, then a fallback.
 */
export function getAxiosErrorMessage(
  err: unknown,
  fallback = "An unknown error occurred",
): string {
  if (axios.isAxiosError(err)) {
    return extractDetail(err.response?.data) || err.message || fallback;
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}
