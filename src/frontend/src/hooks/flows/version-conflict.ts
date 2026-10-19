import type { ConflictDetail } from "@/stores/flowConflictStore";

/** The detail of a 409 that refused a write built on a replaced version, or null. */
// biome-ignore lint/suspicious/noExplicitAny: axios error shape
export const versionConflictDetail = (error: any): ConflictDetail | null => {
  const detail = error?.response?.data?.detail;
  return error?.response?.status === 409 &&
    detail?.code === "flow_version_conflict"
    ? detail
    : null;
};
