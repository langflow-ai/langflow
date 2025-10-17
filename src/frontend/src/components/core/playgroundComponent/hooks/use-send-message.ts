import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { addUserMessage } from "@/utils/messageUtils";
import { useGetFlowId } from "./use-get-flow-id";

export const useSendMessage = () => {
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const chatInputId = useFlowStore(
    useShallow(
      (state) => state.nodes.find((node) => node.data.type === "ChatInput")?.id,
    ),
  );
  const flowId = useGetFlowId();
  const selectedSession = usePlaygroundStore((state) => state.selectedSession);
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);

  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const isPlayground = usePlaygroundStore((state) => state.isPlayground);

  const { data: sessions, refetch } = useGetSessionsFromFlowQuery({
    flowId: currentFlowId,
    useLocalStorage: isPlayground,
  });

  const sendMessage = useCallback(
    async ({
      inputValue,
      files,
    }: {
      inputValue: string;
      files?: string[];
    }): Promise<void> => {
      addUserMessage({
        id: null,
        flow_id: currentFlowId,
        session_id: selectedSession ?? flowId,
        text: inputValue,
        sender: "User",
        sender_name: "User",
        timestamp: new Date().toISOString(),
        files: files ?? [],
        edit: false,
      });
      await buildFlow({
        input_value: inputValue,
        startNodeId: chatInputId,
        files: files,
        silent: true,
        session: selectedSession,
        eventDelivery: eventDeliveryConfig,
      }).catch((err) => {
        console.error(err);
        throw err;
      });
      if (selectedSession && !sessions?.includes(selectedSession)) {
        refetch(); // refetch sessions to add the new session
      }
    },
    [
      buildFlow,
      chatInputId,
      currentFlowId,
      flowId,
      selectedSession,
      eventDeliveryConfig,
      sessions,
      refetch,
    ],
  );

  return { sendMessage };
};
