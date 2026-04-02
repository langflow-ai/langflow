import axios from "axios";

/**
 * Extracts a user-friendly error message from an unknown catch value.
 * Prefers `response.data.detail` for Axios errors, then `.message`, then a fallback.
 */
export function getAxiosErrorMessage(
  err: unknown,
  fallback = "An unknown error occurred",
): string {
  if (axios.isAxiosError(err)) {
    return (
      (err.response?.data as { detail?: string })?.detail ||
      err.message ||
      fallback
    );
  }
  if (err instanceof Error) {
    return err.message;
  }
  return fallback;
}
