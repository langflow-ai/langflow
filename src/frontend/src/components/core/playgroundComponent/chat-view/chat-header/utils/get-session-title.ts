export function getSessionTitle(
  currentSessionId?: string,
  currentFlowId?: string,
): string {
  if (!currentSessionId || currentSessionId === currentFlowId) {
    return "Default Session";
  }
  return currentSessionId;
}
