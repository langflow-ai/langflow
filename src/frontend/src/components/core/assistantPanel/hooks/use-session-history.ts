/**
 * Manages saved assistant sessions: persist, switch, and delete.
 */

import { useCallback, useState } from "react";
import {
  ASSISTANT_MAX_SESSIONS,
  ASSISTANT_SESSIONS_STORAGE_KEY,
  ASSISTANT_SESSION_PREVIEW_LENGTH,
} from "../assistant-panel.constants";
import type {
  AssistantMessage,
  SessionHistoryEntry,
} from "../assistant-panel.types";
import {
  deserializeMessages,
  loadSessionsFromStorage,
  saveSessionsToStorage,
  serializeMessages,
} from "../helpers/session-storage";

interface UseSessionHistoryReturn {
  sessions: SessionHistoryEntry[];
  saveCurrentSession: () => void;
  switchSession: (targetSessionId: string) => void;
  deleteSession: (sessionId: string) => void;
}

export function useSessionHistory(
  currentSessionId: string,
  currentMessages: AssistantMessage[],
  loadSession: (id: string, msgs: AssistantMessage[]) => void,
): UseSessionHistoryReturn {
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>(() =>
    loadSessionsFromStorage(ASSISTANT_SESSIONS_STORAGE_KEY),
  );

  const saveCurrentSession = useCallback(() => {
    if (currentMessages.length === 0) return;

    const firstUserMsg = currentMessages.find((m) => m.role === "user");
    const preview = firstUserMsg
      ? firstUserMsg.content.slice(0, ASSISTANT_SESSION_PREVIEW_LENGTH)
      : "New conversation";

    const entry: SessionHistoryEntry = {
      sessionId: currentSessionId,
      firstUserMessage: preview,
      messageCount: currentMessages.length,
      lastActiveAt: new Date().toISOString(),
      messages: serializeMessages(currentMessages),
    };

    setSessions((prev) => {
      const existingIndex = prev.findIndex(
        (s) => s.sessionId === currentSessionId,
      );
      let updated: SessionHistoryEntry[];
      if (existingIndex >= 0) {
        // Update in-place to preserve order
        updated = prev.map((s) =>
          s.sessionId === currentSessionId ? entry : s,
        );
      } else {
        // New session goes to the top
        updated = [entry, ...prev].slice(0, ASSISTANT_MAX_SESSIONS);
      }
      saveSessionsToStorage(ASSISTANT_SESSIONS_STORAGE_KEY, updated);
      return updated;
    });
  }, [currentSessionId, currentMessages]);

  const switchSession = useCallback(
    (targetSessionId: string) => {
      // Save current before switching
      if (currentMessages.length > 0) {
        saveCurrentSession();
      }

      const target = sessions.find((s) => s.sessionId === targetSessionId);
      if (!target) return;

      const restoredMessages = deserializeMessages(target.messages);
      loadSession(targetSessionId, restoredMessages);
    },
    [sessions, currentMessages, saveCurrentSession, loadSession],
  );

  const deleteSession = useCallback((sessionId: string) => {
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.sessionId !== sessionId);
      saveSessionsToStorage(ASSISTANT_SESSIONS_STORAGE_KEY, filtered);
      return filtered;
    });
  }, []);

  return { sessions, saveCurrentSession, switchSession, deleteSession };
}
