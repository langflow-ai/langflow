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
};

export const useGetAddSessions: UseGetAddSessionsReturnType = ({ flowId }) => {
  const { isPlayground } = usePlaygroundStore();

  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession,
  );

  const selectedSession = usePlaygroundStore((state) => state.selectedSession);

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const addNewSession =
    selectedSession && !dbSessions?.includes(selectedSession)
      ? undefined
      : () => {
          const newSessionId = `${NEW_SESSION_NAME} ${dbSessions?.length ?? 0}`;
          setSelectedSession(newSessionId);
        };

  const sessions = useMemo(() => {
    return (
      dbSessions?.map((sessionId, index) => ({
        id: `session-${index}`, // provide id based on index to not re-render on rename
        sessionId: sessionId,
      })) ?? []
    );
  }, [dbSessions]);

  return {
    addNewSession,
    sessions,
  };
};
