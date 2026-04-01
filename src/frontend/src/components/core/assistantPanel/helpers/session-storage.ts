/**
 * Serialization and deserialization of assistant sessions for localStorage.
 */

import type {
  AssistantMessage,
  SerializedAssistantMessage,
  SessionHistoryEntry,
} from "../assistant-panel.types";

export function loadSessionsFromStorage(
  storageKey: string,
): SessionHistoryEntry[] {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

export function saveSessionsToStorage(
  storageKey: string,
  sessions: SessionHistoryEntry[],
): void {
  try {
    localStorage.setItem(storageKey, JSON.stringify(sessions));
  } catch {
    // localStorage may be full or unavailable
  }
}

export function serializeMessages(
  messages: AssistantMessage[],
): SerializedAssistantMessage[] {
  return messages.map((msg) => {
    const { timestamp, progress, result, ...rest } = msg;
    const serialized: SerializedAssistantMessage = {
      ...rest,
      timestamp: timestamp.toISOString(),
      // Streaming/pending messages become cancelled when session is saved
      status:
        msg.status === "streaming" || msg.status === "pending"
          ? "cancelled"
          : msg.status,
    };
    if (result) {
      serialized.result = result;
    }
    return serialized;
  });
}

export function deserializeMessages(
  serialized: SerializedAssistantMessage[],
): AssistantMessage[] {
  return serialized.map((msg) => ({
    ...msg,
    timestamp: new Date(msg.timestamp),
  }));
}
