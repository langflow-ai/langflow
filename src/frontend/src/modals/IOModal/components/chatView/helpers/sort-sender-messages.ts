import { parseApiTimestamp } from "@/utils/dateTime";
import type { ChatMessageType } from "../../../../../types/chat";

const timestampCache = new WeakMap<ChatMessageType, number>();

// parseApiTimestamp: WebKit rejects the backend "%Y-%m-%d %H:%M:%S.%f %Z" format
const parseTimestamp = (message: ChatMessageType): number =>
  parseApiTimestamp(message.timestamp)?.getTime() ?? 0;

const getCachedTimestamp = (message: ChatMessageType): number => {
  let time = timestampCache.get(message);
  if (time === undefined) {
    time = parseTimestamp(message);
    timestampCache.set(message, time);
  }
  return time;
};

/**
 * Sorts chat messages chronologically; on identical (or unparseable)
 * timestamps, user messages come before AI/Machine messages.
 */
const sortSenderMessages = (a: ChatMessageType, b: ChatMessageType): number => {
  const timeA = getCachedTimestamp(a);
  const timeB = getCachedTimestamp(b);

  if (timeA !== timeB) {
    return timeA - timeB;
  }

  if (a.isSend && !b.isSend) {
    return -1;
  }
  if (!a.isSend && b.isSend) {
    return 1;
  }

  return 0;
};

export default sortSenderMessages;
