const COLLABORATION_OPERATION_BETA_STORAGE_KEY =
  "langflow_collaboration_operation_beta";

export function readCollaborationOperationBetaEnabled(): boolean {
  if (typeof window === "undefined") {
    return false;
  }
  return (
    window.localStorage.getItem(COLLABORATION_OPERATION_BETA_STORAGE_KEY) ===
    "true"
  );
}

export function writeCollaborationOperationBetaEnabled(enabled: boolean): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(
    COLLABORATION_OPERATION_BETA_STORAGE_KEY,
    enabled ? "true" : "false",
  );
}
