import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import useFlowStore from "@/stores/flowStore";
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
    },
    [buildFlow, chatInputId, selectedSession, eventDeliveryConfig],
  );

  return { sendMessage };
};
