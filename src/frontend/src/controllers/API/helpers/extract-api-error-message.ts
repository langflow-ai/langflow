/**
 * Extracts a human-readable error message from an Axios error response.
 *
 * FastAPI validation errors return `detail` as an array of objects
 * (e.g. [{type, loc, msg, input, ctx}]). Directly coercing these
 * to a string produces "[object Object]". This helper normalises
 * all known shapes of `detail` into a readable string.
 */
export function extractApiErrorMessage(
  error: { response?: { data?: { detail?: unknown } }; message?: string },
  fallback: string,
): string {
  const detail = error.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    return detail
      .map((d: Record<string, unknown>) =>
        typeof d.msg === "string" ? d.msg : String(d),
      )
      .join("; ");
  }

  if (detail && typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.msg === "string") return obj.msg;
    if (typeof obj.message === "string") return obj.message;
    return JSON.stringify(detail);
  }

  return error.message || fallback;
}
