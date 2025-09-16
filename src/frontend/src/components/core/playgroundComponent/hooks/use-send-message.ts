import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { useGetSessionsFromFlowQuery } from "@/controllers/API/queries/messages/use-get-sessions-from-flow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { usePlaygroundStore } from "@/stores/playgroundStore";
import { useUtilityStore } from "@/stores/utilityStore";

export const useSendMessage = () => {
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const chatInputId = useFlowStore(
    useShallow(
      (state) => state.nodes.find((node) => node.data.type === "ChatInput")?.id,
    ),
  );
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
        refetch();
      }
    },
    [
      buildFlow,
      chatInputId,
      selectedSession,
      eventDeliveryConfig,
      sessions,
      refetch,
    ],
  );

  return { sendMessage };
};
