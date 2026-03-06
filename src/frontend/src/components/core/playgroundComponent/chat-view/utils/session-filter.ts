import type { Message } from "@/types/messages";

/**
 * Determines if a message belongs to a specific session.
 *
 * Why this logic exists:
 * - Default session (sessionId === flowId): Shows messages with matching session_id OR no session_id (legacy)
 * - Named sessions: Only shows messages with exact session_id match
 * - This prevents cross-session data leakage after deletions
 *
 * @param msg - The message to check
 * @param flowId - The current flow ID
 * @param sessionId - The session ID to filter for (null means no filtering)
 * @returns true if the message belongs to the session
 */
export function isMessageForSession(
  msg: Message,
  flowId: string,
  sessionId: string | null,
): boolean {
  if (!sessionId) return false;

  const isCurrentFlow = msg.flow_id === flowId;

  if (sessionId === flowId) {
    // Default session: include messages with matching session_id or no session_id (legacy behavior)
    return isCurrentFlow && (msg.session_id === sessionId || !msg.session_id);
  }

  return isCurrentFlow && msg.session_id === sessionId;
}
