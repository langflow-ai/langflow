import type { ChatMessageType } from "../../../../../types/chat";

/**
 * Sorts chat messages by timestamp with proper handling of identical timestamps.
 *
 * Primary sort: By timestamp (chronological order)
 * Secondary sort: When timestamps are identical, User messages (isSend=true) come before AI/Machine messages (isSend=false)
 *
 * This ensures proper conversation flow even when backend generates identical timestamps
 * due to streaming, load balancing, or database precision limitations.
 *
 * @param a - First chat message to compare
 * @param b - Second chat message to compare
 * @returns Sort comparison result (-1, 0, 1)
 */
const sortSenderMessages = (a: ChatMessageType, b: ChatMessageType): number => {
  const timeA = new Date(a.timestamp).getTime();
  const timeB = new Date(b.timestamp).getTime();

  // Primary sort: by timestamp
  if (timeA !== timeB) {
    return timeA - timeB;
  }

  // Secondary sort: if timestamps are identical, User messages come before AI/Machine
  // This ensures proper chronological order when backend generates identical timestamps
  if (a.isSend && !b.isSend) {
    return -1; // User message (isSend=true) comes first
  }
  if (!a.isSend && b.isSend) {
    return 1; // User message (isSend=true) comes first
  }

  return 0; // Keep original order for same sender types
};

export default sortSenderMessages;
