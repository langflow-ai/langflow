import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { usePlaygroundStore } from "@/stores/playgroundStore";

const LOCAL_SESSIONS_STORAGE_KEY = (flowId: string) =>
  `langflow_local_sessions_${flowId}`;

export const useEditSessionInfo = ({
  flowId,
  dbSessions: providedDbSessions,
  renameLocalSession,
}: {
  flowId?: string;
  dbSessions?: string[];
  renameLocalSession?: (oldSessionId: string, newSessionId: string) => void;
}) => {
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession,
  );
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  // Only fetch if dbSessions not provided (to avoid duplicate queries)
  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery(
    {
      id: flowId,
    },
    {
      enabled: providedDbSessions === undefined,
    },
  );
  const dbSessions = providedDbSessions ?? dbSessionsResponse?.sessions ?? [];

  const { mutateAsync: updateSessionName } = useUpdateSessionName();

  const { mutate: deleteSession } = useDeleteSession();

  const handleDelete = (sessionId: string) => {
    if (sessionId && dbSessions.includes(sessionId)) {
      deleteSession({ sessionId: sessionId });
    }
    if (flowId && sessionId === selectedSession) {
      setSelectedSession(flowId);
    }
  };

  const handleRename = async (sessionId: string, newSessionId: string) => {
    // Update session name via API or sessionStorage
    await updateSessionName({
      old_session_id: sessionId,
      new_session_id: newSessionId,
    });

    // Update local sessions list using the provided function
    if (renameLocalSession) {
      renameLocalSession(sessionId, newSessionId);
    }

    // Update selected session if the renamed session is currently selected
    if (flowId && sessionId === selectedSession) {
      setSelectedSession(newSessionId);
    }
  };

  return {
    handleRename,
    handleDelete,
  };
};
