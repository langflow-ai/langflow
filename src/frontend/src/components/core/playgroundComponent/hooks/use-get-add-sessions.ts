import { useMemo } from "react";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export interface SessionInfo {
  id: string;
  sessionId: string;
}

interface UseGetAddSessionsProps {
  flowId?: string;
}

type UseGetAddSessionsReturnType = (props: UseGetAddSessionsProps) => {
  addNewSession: (() => void) | undefined;
  sessions: SessionInfo[];
};

const LOCAL_NEW_SESSION_NAME = "New chat";

export const useGetAddSessions: UseGetAddSessionsReturnType = ({ flowId }) => {
  const { isPlayground } = usePlaygroundStore();

  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession,
  );

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);

  const { data: dbSessionsResponse } = useGetSessionsFromFlowQuery({
    id: flowId,
  });
  const dbSessions: string[] = dbSessionsResponse?.sessions ?? [];

  const addNewSession: (() => void) | undefined =
    selectedSession && !dbSessions.includes(selectedSession)
      ? undefined
      : () => {
          const newSessionId = `${LOCAL_NEW_SESSION_NAME} ${
            dbSessions.length ?? 0
          }`;
          setSelectedSession(newSessionId);
        };

  const sessions: SessionInfo[] = useMemo(() => {
    return dbSessions.map((sessionId, index) => ({
      id: `session-${index}`, // provide id based on index to not re-render on rename
      sessionId,
    }));
  }, [dbSessions]);

  return {
    addNewSession,
    sessions,
  };
};
