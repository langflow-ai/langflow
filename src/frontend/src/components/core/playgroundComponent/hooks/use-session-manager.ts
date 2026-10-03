import { useCallback, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { v4 as uuidv4 } from "uuid";
import { useShallow } from "zustand/react/shallow";
import { NEW_SESSION_NAME } from "@/constants/constants";
import { useBulkDeleteSessions } from "@/controllers/API/queries/messages/use-bulk-delete-sessions";
import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import useAlertStore from "@/stores/alertStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";
import { clearSessionMessages } from "../chat-view/utils/message-utils";

interface UseSessionManagerProps {
  flowId?: string;
}

const EMPTY_SESSIONS: string[] = [];

export function useSessionManager({ flowId }: UseSessionManagerProps) {
  // Select individual actions (stable references) and state slices to avoid
  // re-rendering on every store change.
  const initialize = useSessionManagerStore((s) => s.initialize);
  const addSession = useSessionManagerStore((s) => s.addSession);
  const setActiveSessionId = useSessionManagerStore(
    (s) => s.setActiveSessionId,
  );
  const removeSession = useSessionManagerStore((s) => s.removeSession);
  const renameSessionInStore = useSessionManagerStore((s) => s.renameSession);
  const syncFromServer = useSessionManagerStore((s) => s.syncFromServer);
  const activeSessionIdFromStore = useSessionManagerStore(
    (s) => s.activeSessionId,
  );
  const sessions = useSessionManagerStore(
    useShallow((s) => s.getOrderedSessionIds()),
  );

  const deleteSessionFromMessagesStore = useMessagesStore(
    (state) => state.deleteSession,
  );
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const sessionsQuery = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const fetchedSessions = sessionsQuery.data?.sessions ?? EMPTY_SESSIONS;

  const { mutate: deleteSessionApi } = useDeleteSession({});
  const { mutate: bulkDeleteSessionsApi } = useBulkDeleteSessions();
  const { mutateAsync: updateSessionName } = useUpdateSessionName();

  const notifyDeleteSessionError = useCallback(() => {
    setErrorData({ title: t("errors.deleteSession") });
  }, [setErrorData, t]);

  // Initialize store when flowId changes
  useEffect(() => {
    if (flowId) {
      initialize(flowId);
    }
  }, [flowId, initialize]);

  // Only the pages for the current query scope are applied. While a new
  // flow or identity loads, clear the previous server sessions.
  useEffect(() => {
    if (!flowId) return;
    syncFromServer(fetchedSessions);
  }, [flowId, fetchedSessions, syncFromServer]);

  const activeSessionId = activeSessionIdFromStore ?? flowId;

  const createSession = useCallback(() => {
    if (!flowId) return;
    // Older sessions may not be loaded, so an incrementing name derived from
    // the visible list could accidentally reopen an existing conversation.
    const newId = `${NEW_SESSION_NAME} ${uuidv4()}`;

    addSession({ id: newId, isLocal: true });
    setActiveSessionId(newId);
    clearSessionMessages(newId, flowId);
  }, [flowId, addSession, setActiveSessionId]);

  const deleteSession = useCallback(
    (sessionId: string) => {
      if (!flowId) return;
      // Always attempt API delete — the sessions query isn't invalidated
      // after sending a message, so isLocal may never get promoted. A 404
      // for a truly local-only session is harmless.
      deleteSessionApi(
        { sessionId, flowId },
        {
          onError: notifyDeleteSessionError,
        },
      );
      clearSessionMessages(sessionId, flowId);
      deleteSessionFromMessagesStore(sessionId);
      removeSession(sessionId);
    },
    [
      flowId,
      deleteSessionApi,
      deleteSessionFromMessagesStore,
      notifyDeleteSessionError,
      removeSession,
    ],
  );

  const deleteSessionLocalOnly = useCallback(
    (sessionId: string) => {
      if (!flowId) return;
      // Local cleanup only - no API call (used after bulk delete)
      clearSessionMessages(sessionId, flowId);
      deleteSessionFromMessagesStore(sessionId);
      removeSession(sessionId);
    },
    [flowId, deleteSessionFromMessagesStore, removeSession],
  );

  const renameSession = useCallback(
    async (oldId: string, newId: string) => {
      try {
        await updateSessionName({
          old_session_id: oldId,
          new_session_id: newId,
        });
        renameSessionInStore(oldId, newId);
      } catch {
        setErrorData({ title: t("errors.renamingSession") });
      }
    },
    [updateSessionName, renameSessionInStore, setErrorData],
  );

  const selectSession = useCallback(
    (sessionId: string) => {
      setActiveSessionId(sessionId);
    },
    [setActiveSessionId],
  );

  const clearDefaultSession = useCallback(() => {
    if (!flowId) return;
    deleteSessionApi(
      { sessionId: flowId, flowId },
      {
        onSuccess: () => {
          clearSessionMessages(flowId, flowId);
        },
        onError: notifyDeleteSessionError,
      },
    );
  }, [flowId, deleteSessionApi, notifyDeleteSessionError]);

  const bulkDeleteSessions = useCallback(
    (sessionIds: string[], onSuccess?: () => void) => {
      if (!flowId || sessionIds.length === 0) return;

      // Separate local-only sessions from server sessions
      const serverSessions = sessionIds.filter((sessionId) =>
        fetchedSessions.includes(sessionId),
      );

      // Perform local cleanup for all sessions
      sessionIds.forEach((sessionId) => {
        deleteSessionLocalOnly(sessionId);
      });

      // Only call API if there are server sessions
      if (serverSessions.length > 0) {
        bulkDeleteSessionsApi(
          { sessionIds: serverSessions },
          {
            onSuccess: () => onSuccess?.(),
            onError: notifyDeleteSessionError,
          },
        );
      } else {
        // All sessions are local-only, call success immediately
        onSuccess?.();
      }
    },
    [
      flowId,
      fetchedSessions,
      bulkDeleteSessionsApi,
      deleteSessionFromMessagesStore,
      notifyDeleteSessionError,
      removeSession,
    ],
  );

  return {
    activeSessionId,
    sessions,
    fetchedSessions,
    hasMoreSessions: sessionsQuery.hasNextPage,
    isLoadingSessions: sessionsQuery.isFetchingNextPage,
    loadMoreSessions: () => {
      if (sessionsQuery.hasNextPage && !sessionsQuery.isFetching) {
        void sessionsQuery.fetchNextPage();
      }
    },
    createSession,
    deleteSession,
    deleteSessionLocalOnly,
    bulkDeleteSessions,
    renameSession,
    selectSession,
    clearDefaultSession,
  };
}
