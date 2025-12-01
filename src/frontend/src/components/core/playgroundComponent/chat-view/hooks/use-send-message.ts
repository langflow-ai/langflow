import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";

interface UseSendMessageProps {
  sessionId?: string;
}

export const useSendMessage = ({ sessionId }: UseSendMessageProps = {}) => {
  const buildFlow = useFlowStore((state) => state.buildFlow);
  const chatInputId = useFlowStore(
    useShallow(
      (state) => state.nodes.find((node) => node.data.type === "ChatInput")?.id,
    ),
  );
  const eventDeliveryConfig = useUtilityStore((state) => state.eventDelivery);
  const setAwaitingBotResponse = useUtilityStore(
    (state) => state.setAwaitingBotResponse,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const sendMessage = useCallback(
    async ({
      inputValue,
      files,
    }: {
      inputValue: string;
      files?: string[];
    }): Promise<void> => {
      // Set flag before sending - bot response should animate
      setAwaitingBotResponse(true);

      await buildFlow({
        input_value: inputValue,
        startNodeId: chatInputId,
        files: files,
        silent: true,
        session: sessionId ?? currentFlowId,
        eventDelivery: eventDeliveryConfig,
      }).catch((err) => {
        console.error(err);
        setAwaitingBotResponse(false);
        throw err;
      });
    },
    [
      buildFlow,
      chatInputId,
      sessionId,
      currentFlowId,
      eventDeliveryConfig,
      setAwaitingBotResponse,
    ],
  );

  return { sendMessage };
};
