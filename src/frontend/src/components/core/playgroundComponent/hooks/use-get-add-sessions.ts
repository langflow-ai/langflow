import { useMemo } from "react";
import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { usePlaygroundStore } from "@/stores/playgroundStore";

interface SessionInfo {
  id: string;
  sessionId: string;
}

interface UseGetAddSessionsProps {
  flowId?: string;
}

type UseGetAddSessionsReturnType = (props: UseGetAddSessionsProps) => {
  addNewSession: (() => void) | undefined;
  sessions: SessionInfo[];
  selectedSession: string | undefined;
};

export const useGetAddSessions: UseGetAddSessionsReturnType = ({ flowId }) => {
  const { isPlayground } = usePlaygroundStore();

  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession,
  );

  const explicitSelectedSession = usePlaygroundStore(
    (state) => state.selectedSession,
  );

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });
  const hasExplicitSelection =
    explicitSelectedSession && explicitSelectedSession !== flowId;

  const selectedSession = hasExplicitSelection
    ? explicitSelectedSession
    : dbSessions && dbSessions.length > 0
      ? dbSessions[dbSessions.length - 1]
      : flowId;

  const addNewSession =
    selectedSession && !dbSessions?.includes(selectedSession)
      ? undefined
      : () => {
          const newSessionId = `${NEW_SESSION_NAME} ${dbSessions?.length ?? 0}`;
          setSelectedSession(newSessionId);
        };

  const sessions = useMemo(() => {
    if (!dbSessions) return [];

    // Filter out flowId (default session) if there are multiple sessions
    const filteredSessions =
      dbSessions.length > 1
        ? dbSessions.filter((sessionId) => sessionId !== flowId)
        : dbSessions;

    return filteredSessions.map((sessionId, index) => ({
      id: `session-${index}`, // provide id based on index to not re-render on rename
      sessionId: sessionId,
    }));
  }, [dbSessions, flowId]);

  return {
    addNewSession,
    sessions,
    selectedSession,
  };
};
