import i18n from "@/i18n";

export function getSessionTitle(
  currentSessionId?: string,
  currentFlowId?: string,
): string {
  if (!currentSessionId || currentSessionId === currentFlowId) {
    return i18n.t("playground.defaultSession");
  }
  return currentSessionId;
}
