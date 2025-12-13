import type { AxiosError } from "axios";

export function isNoMessagesError(error: unknown): boolean {
  if (!error) {
    return false;
  }

  const axiosError = error as AxiosError<{ detail?: string }>;
  const detail = axiosError?.response?.data?.detail;

  return typeof detail === "string" && detail.includes("No messages found");
}
