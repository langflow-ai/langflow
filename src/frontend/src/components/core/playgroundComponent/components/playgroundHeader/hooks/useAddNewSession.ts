import { useShallow } from "zustand/react/shallow";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";

export const useAddNewSession = () => {
  const setSelectedSession = usePlaygroundStore(
    (state) => state.setSelectedSession
  );
  const flowId = useFlowStore(useShallow((state) => state.currentFlow?.id));
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  const { data: sessions } = useGetSessionsFromFlowQuery({
    flowId: flowId,
    useLocalStorage: isPlayground,
  });

  const addSession = () => {
    if (!sessions) {
      return;
    }

    const newSessionId = `New Chat ${sessions?.length ?? 0}`;
    setSelectedSession(newSessionId);
  };

  return addSession;
};
