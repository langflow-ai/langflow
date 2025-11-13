import type { ChatMessageType } from "../../../../../types/chat";

// Cache parsed timestamps to avoid repeatedly parsing identical values
const messageTimestampCache = new WeakMap<ChatMessageType, number>();
const timestampValueCache = new Map<string, number>();

const parseTimestamp = (timestamp: string): number => {
  const cached = timestampValueCache.get(timestamp);
  if (cached !== undefined) {
    return cached;
  }

  // Date.parse is slightly faster than instantiating a Date object
  let parsed = Date.parse(timestamp);

  if (Number.isNaN(parsed)) {
    parsed = new Date(timestamp).getTime();
  }

  timestampValueCache.set(timestamp, parsed);
  return parsed;
};

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
  // Use WeakMap cache to avoid repeated Date parsing for same message objects
  let timeA = messageTimestampCache.get(a);
  if (timeA === undefined) {
    timeA = parseTimestamp(a.timestamp);
    messageTimestampCache.set(a, timeA);
  }

  let timeB = messageTimestampCache.get(b);
  if (timeB === undefined) {
    timeB = parseTimestamp(b.timestamp);
    messageTimestampCache.set(b, timeB);
  }

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
