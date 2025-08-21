import { useDeleteSession } from "@/controllers/API/queries/messages/use-delete-sessions";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { useUpdateSessionName } from "@/controllers/API/queries/messages/use-rename-session";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export const useEditSessionInfo = ({ flowId }: { flowId?: string }) => {
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: updateSessionName } = useUpdateSessionName({
    flowId,
    useLocalStorage: isPlayground,
  });

  const { mutate: deleteSession } = useDeleteSession({
    flowId,
    useLocalStorage: isPlayground,
  });

  const handleDelete = (sessionId: string) => {
    if (sessionId && dbSessions?.includes(sessionId)) {
      deleteSession({ sessionId: sessionId });
    }
    setSelectedSession(flowId);
  };

  const handleRename = (sessionId: string, newSessionId: string) => {
    if (dbSessions?.includes(sessionId)) {
      updateSessionName({
        oldSessionId: sessionId,
        newSessionId,
      });
    }
    setSelectedSession(newSessionId);
  };

  return {
    handleRename,
    handleDelete,
  };
};
