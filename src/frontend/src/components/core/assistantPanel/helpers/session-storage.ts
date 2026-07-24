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
    // flowProposalSnapshot is a full canvas clone that can blow the storage
    // quota; cross-reload revert is covered by the restore-point path instead.
    const {
      timestamp,
      progress,
      result,
      inProgressTask,
      flowProposalSnapshot,
      ...rest
    } = msg;
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
    // The spinner row is transient — persisting it stuck restored sessions.
    // Error messages keep it on purpose (frozen "where it stopped" row).
    if (msg.status === "error" && inProgressTask) {
      serialized.inProgressTask = inProgressTask;
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
