import { findHumanInputContent } from "@/controllers/API/agui/human-input-card";
import type { ChatMessageType } from "@/types/chat";

/**
 * Whether a newly appended chat message must force the view to scroll to it.
 * User sends always do; content that demands a user action (an unanswered
 * human-input card) must too, or the run looks stuck below the fold.
 */
export function shouldForceScrollOnNewMessage(
  lastMsg: ChatMessageType | undefined,
): boolean {
  if (!lastMsg) return false;
  if (lastMsg.isSend) return true;
  const humanInput = findHumanInputContent(lastMsg.content_blocks);
  return Boolean(humanInput && !humanInput.submitted_action);
}
