import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useMemo } from "react";
import { useShallow } from "zustand/react/shallow";

export const useGetAddSessions = () => {
  const { isPlayground } = usePlaygroundStore();

  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const { data: dbSessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const addNewSession = () => {
    const newSessionId = `${NEW_SESSION_NAME} ${dbSessions?.length ?? 0}`;
    setSelectedSession(newSessionId);
  };

  const sessions = useMemo(() => {
    if (!selectedSession || dbSessions?.includes(selectedSession)) {
      return dbSessions;
    }
    return [...(dbSessions || []), selectedSession];
  }, [dbSessions, selectedSession]);

  return {
    addNewSession,
    sessions,
  };
};
