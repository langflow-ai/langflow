import type { ChatMessageType } from "@/types/chat";

/**
 * Sorts chat messages by timestamp.
 * When timestamps are identical, user messages come before bot messages.
 */
const sortSenderMessages = (a: ChatMessageType, b: ChatMessageType): number => {
  const timeA = new Date(a.timestamp).getTime();
  const timeB = new Date(b.timestamp).getTime();

  if (timeA !== timeB) {
    return timeA - timeB;
  }

  // Same timestamp: user messages (isSend=true) come first
  return Number(b.isSend) - Number(a.isSend);
};

export default sortSenderMessages;
