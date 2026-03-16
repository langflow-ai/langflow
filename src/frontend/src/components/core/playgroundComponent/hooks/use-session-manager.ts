import { useCallback, useEffect } from "react";
import { NEW_SESSION_NAME } from "@/constants/constants";
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
  const getOrderedSessionIds = useSessionManagerStore(
    (s) => s.getOrderedSessionIds,
  );
  const activeSessionIdFromStore = useSessionManagerStore(
    (s) => s.activeSessionId,
  );

  const deleteSessionFromMessagesStore = useMessagesStore(
    (state) => state.deleteSession,
  );
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const fetchedSessions = dbSessionsResponse?.sessions ?? [];

  const { mutate: deleteSessionApi } = useDeleteSession({});
  const { mutateAsync: updateSessionName } = useUpdateSessionName();

  const notifyDeleteSessionError = useCallback(() => {
    setErrorData({ title: "Error deleting session." });
  }, [setErrorData]);

  // Initialize store when flowId changes
  useEffect(() => {
    if (flowId) {
      initialize(flowId);
    }
  }, [flowId, initialize]);

  // Sync server sessions into store (include flowId in deps to avoid stale
  // data from keepPreviousData during flow switches)
  useEffect(() => {
    if (!flowId) return;
    syncFromServer(fetchedSessions);
  }, [flowId, fetchedSessions, syncFromServer]);

  const sessions = getOrderedSessionIds();
  const activeSessionId = activeSessionIdFromStore ?? flowId;

  const createSession = useCallback(() => {
    if (!flowId) return;
    const newSessionPattern = new RegExp(`^${NEW_SESSION_NAME} (\\d+)$`);
    const allSessions = getOrderedSessionIds();
    const existingNumbers = allSessions
      .map((s) => {
        const match = s.match(newSessionPattern);
        return match ? parseInt(match[1], 10) : -1;
      })
      .filter((n) => n >= 0);
    const nextNumber =
      existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : 0;
    const newId = `${NEW_SESSION_NAME} ${nextNumber}`;

    addSession({ id: newId, isLocal: true });
    setActiveSessionId(newId);
    clearSessionMessages(newId, flowId);
  }, [flowId, getOrderedSessionIds, addSession, setActiveSessionId]);

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

  const renameSession = useCallback(
    async (oldId: string, newId: string) => {
      try {
        await updateSessionName({
          old_session_id: oldId,
          new_session_id: newId,
        });
        renameSessionInStore(oldId, newId);
      } catch {
        setErrorData({ title: "Error renaming session." });
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

  return {
    activeSessionId,
    sessions,
    fetchedSessions,
    createSession,
    deleteSession,
    renameSession,
    selectSession,
    clearDefaultSession,
  };
}
