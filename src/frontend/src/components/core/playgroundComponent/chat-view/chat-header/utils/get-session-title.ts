export function getSessionTitle(
  currentSessionId?: string,
  currentFlowId?: string,
): string {
  if (!currentSessionId) {
    return "Chat";
  }
  if (currentSessionId === currentFlowId) {
    return "Default Session";
  }
  return currentSessionId;
}
