/**
 * Manages saved assistant sessions: persist, switch, and delete.
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>(() =>
    loadSessionsFromStorage(ASSISTANT_SESSIONS_STORAGE_KEY),
  );

  const saveCurrentSession = useCallback(() => {
    if (currentMessages.length === 0) return;

    const firstUserMsg = currentMessages.find((m) => m.role === "user");
    const preview = firstUserMsg
      ? firstUserMsg.content.slice(0, ASSISTANT_SESSION_PREVIEW_LENGTH)
      : t("assistant.newConversation");

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

  // WS-6 / RC-7: persist the current session as soon as a turn settles —
  // not only on the explicit New session click. Without this a panel close
  // or page reload loses the session (report #5: "new session lost", "only
  // the last two kept"). We persist only when no message is in flight so a
  // half-streamed turn isn't written every token; the in-place merge in
  // saveCurrentSession keeps a single up-to-date entry per session.
  const hasInFlightMessage = currentMessages.some(
    (m) => m.status === "streaming" || m.status === "pending",
  );
  useEffect(() => {
    if (currentMessages.length === 0 || hasInFlightMessage) return;
    saveCurrentSession();
  }, [currentMessages, hasInFlightMessage, saveCurrentSession]);

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
