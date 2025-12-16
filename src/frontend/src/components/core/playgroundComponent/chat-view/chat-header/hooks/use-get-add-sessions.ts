import { useMemo } from "react";
import { NEW_SESSION_NAME } from "@/constants/constants";
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

export const useGetAddSessions: UseGetAddSessionsReturnType = ({ flowId }) => {
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
          const newSessionId = `${NEW_SESSION_NAME} ${dbSessions.length ?? 0}`;
          setSelectedSession(newSessionId);
        };

  const sessions: SessionInfo[] = useMemo(
    () =>
      dbSessions.map((sessionId, index) => ({
        id: `session-${index}`,
        sessionId,
      })),
    [dbSessions],
  );

  return {
    addNewSession,
    sessions,
  };
};
