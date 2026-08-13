import type { ChatMessageType } from "@/types/chat";
import { parseApiTimestamp } from "@/utils/dateTime";

/**
 * Sorts chat messages by timestamp.
 * Timestamps go through parseApiTimestamp because WebKit rejects the backend
 * "%Y-%m-%d %H:%M:%S.%f %Z" format — a raw new Date() would yield NaN there
 * and silently disable the sort.
 * When timestamps are identical or unparseable, user messages come first.
 */
const sortSenderMessages = (a: ChatMessageType, b: ChatMessageType): number => {
  const timeA = parseApiTimestamp(a.timestamp)?.getTime() ?? 0;
  const timeB = parseApiTimestamp(b.timestamp)?.getTime() ?? 0;

  if (timeA !== timeB) {
    return timeA - timeB;
  }

  // Same timestamp: user messages (isSend=true) come first
  return Number(b.isSend) - Number(a.isSend);
};

export default sortSenderMessages;
