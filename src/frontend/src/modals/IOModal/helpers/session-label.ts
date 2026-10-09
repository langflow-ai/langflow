/**
 * Label for a session id in the Playground sidebar and chat header.
 * The shared Playground's backend stores every session as `<virtualFlowId>:<name>`
 * so a public caller cannot address sessions outside its own namespace; ids keep
 * that prefix everywhere, only the label drops it.
 */
export function getSessionLabel(sessionId: string, flowId: string): string {
  const prefix = `${flowId}:`;
  return sessionId.startsWith(prefix) && sessionId.length > prefix.length
    ? sessionId.slice(prefix.length)
    : sessionId;
}
