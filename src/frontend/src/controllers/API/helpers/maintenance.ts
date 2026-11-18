import { isAxiosError } from "axios";

/** Recognize only the server's deliberate external bearer maintenance refusal. */
export function isExternalAuthMaintenanceRefusal(error: unknown): boolean {
  return (
    isAxiosError<{ detail?: { code?: string } }>(error) &&
    error.response?.status === 503 &&
    error.response.data?.detail?.code === "external_auth_maintenance"
  );
}
