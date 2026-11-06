import { useCallback, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useShallow } from "zustand/react/shallow";
import { NEW_SESSION_NAME } from "@/constants/constants";
import { getMessages } from "@/controllers/API/queries/messages";
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

const NO_SESSIONS: string[] = [];

// Candidates step by doubling (see createSession), so 21 checks reach names up
// to 2^19 (524,288) above the first candidate before giving up.
const MAX_SESSION_NAME_CHECKS = 21;

const NEW_SESSION_PATTERN = new RegExp(`^${NEW_SESSION_NAME} (\\d+)$`);

function nextNewSessionNumber(sessionIds: string[]): number {
  const existingNumbers = sessionIds
    .map((s) => {
      const match = s.match(NEW_SESSION_PATTERN);
      return match ? parseInt(match[1], 10) : -1;
    })
    .filter((n) => n >= 0);
  return existingNumbers.length > 0 ? Math.max(...existingNumbers) + 1 : 0;
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
  const sessions = useSessionManagerStore(
    useShallow((s) => s.getOrderedSessionIds()),
  );
  const activeSessionIdFromStore = useSessionManagerStore(
    (s) => s.activeSessionId,
  );

  const deleteSessionFromMessagesStore = useMessagesStore(
    (state) => state.deleteSession,
  );
  const { t } = useTranslation();
  const setErrorData = useAlertStore((state) => state.setErrorData);

  const sessionsQuery = useGetSessionsFromFlowQuery({ id: flowId });
  const fetchedSessions = sessionsQuery.data ?? NO_SESSIONS;
  const allSessionsLoaded =
    sessionsQuery.isSuccess &&
    !sessionsQuery.isPlaceholderData &&
    !sessionsQuery.hasNextPage;
  // Each attempt has its own identity so a stale lookup cannot complete or
  // release the guard for a newer attempt, even for the same flow.
  const creatingSessionFor = useRef<{ flowId: string } | null>(null);

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
    return () => {
      creatingSessionFor.current = null;
    };
  }, [flowId, initialize]);

  // Sync server sessions into the store. While the query shows the previous
  // flow's list as placeholder data (keepPreviousData), there is nothing to
  // sync for this flow yet.
  const isPlaceholderSessions = sessionsQuery.isPlaceholderData;
  useEffect(() => {
    if (!flowId || isPlaceholderSessions) return;
    syncFromServer(fetchedSessions);
  }, [flowId, fetchedSessions, isPlaceholderSessions, syncFromServer]);

  const activeSessionId = activeSessionIdFromStore ?? flowId;

  // Names the session "New Session N" after the highest N in the list. While
  // older pages are not loaded, an unloaded session may already use that name,
  // and reusing a session id reopens its conversation (and the model's memory),
  // so candidates are checked on the server first: N, N+1, N+2, N+4, N+8, ...
  // and the first free one wins (e.g. 0..29 taken: 0, 1, 2, 4, 8, 16, 32).
  const createSession = useCallback(async () => {
    if (!flowId || creatingSessionFor.current?.flowId === flowId) return;
    const startSession = (sessionId: string) => {
      addSession({ id: sessionId, isLocal: true });
      setActiveSessionId(sessionId);
      clearSessionMessages(sessionId, flowId);
    };
    const firstNumber = nextNewSessionNumber(sessions);
    if (allSessionsLoaded) {
      startSession(`${NEW_SESSION_NAME} ${firstNumber}`);
      return;
    }

    const attempt = { flowId };
    creatingSessionFor.current = attempt;
    const isCurrentAttempt = () =>
      creatingSessionFor.current === attempt &&
      useSessionManagerStore.getState().flowId === flowId;
    try {
      for (let check = 0; check < MAX_SESSION_NAME_CHECKS; check++) {
        const step = check === 0 ? 0 : 2 ** (check - 1);
        const candidate = `${NEW_SESSION_NAME} ${firstNumber + step}`;
        const { data } = await getMessages(flowId, {
          session_id: candidate,
          limit: 1,
        });
        if (!isCurrentAttempt()) return;
        if (data.length > 0) continue;
        startSession(candidate);
        return;
      }
      if (isCurrentAttempt())
        setErrorData({ title: t("errors.createSession") });
    } catch {
      if (isCurrentAttempt())
        setErrorData({ title: t("errors.createSession") });
    } finally {
      if (creatingSessionFor.current === attempt) {
        creatingSessionFor.current = null;
      }
    }
  }, [
    flowId,
    sessions,
    allSessionsLoaded,
    addSession,
    setActiveSessionId,
    setErrorData,
    t,
  ]);

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

      // Separate local-only sessions from server sessions. Ask the store, not
      // the loaded pages: the open session can be saved but outside them.
      const localIds = new Set(
        useSessionManagerStore
          .getState()
          .sessions.filter((s) => s.isLocal)
          .map((s) => s.id),
      );
      const serverSessions = sessionIds.filter(
        (sessionId) => !localIds.has(sessionId),
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
    sessionsPagination: sessionsQuery,
    createSession,
    deleteSession,
    deleteSessionLocalOnly,
    bulkDeleteSessions,
    renameSession,
    selectSession,
    clearDefaultSession,
  };
}
