import { NEW_SESSION_NAME } from "@/constants/constants";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export const useGetAddSessions = ({ flowId }: { flowId?: string }) => {
  const { isPlayground } = usePlaygroundStore();

  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );

  const { data: sessions } = useGetSessionsFromFlowQuery({
    flowId,
    useLocalStorage: isPlayground,
  });

  const addNewSession = () => {
    const newSessionId = `${NEW_SESSION_NAME} ${sessions?.length ?? 0}`;
    setSelectedSession(newSessionId);
  };

  return {
    addNewSession,
    sessions,
  };
};
