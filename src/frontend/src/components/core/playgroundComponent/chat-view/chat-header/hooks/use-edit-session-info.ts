import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export const useEditSessionInfo = ({ flowId }: { flowId?: string }) => {
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession,
  );
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const dbSessions = dbSessionsResponse?.sessions ?? [];

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
    if (dbSessions.includes(sessionId)) {
      await updateSessionName({
        old_session_id: sessionId,
        new_session_id: newSessionId,
      });
    }
    if (flowId && sessionId === selectedSession) {
      setSelectedSession(newSessionId);
    }
  };

  return {
    handleRename,
    handleDelete,
  };
};
