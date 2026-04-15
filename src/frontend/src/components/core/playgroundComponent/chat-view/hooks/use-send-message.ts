import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { queryClient } from "@/contexts";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useGetFlowId } from "../../hooks/use-get-flow-id";
import { addUserMessage } from "../utils/message-utils";

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
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);
  const flowId = useGetFlowId();

  const sendMessage = useCallback(
    async ({
      inputValue,
      files,
    }: {
      inputValue: string;
      files?: string[];
    }): Promise<void> => {
      // sessionId is always provided from store's activeSessionId. Fallback to flowId.
      const actualSession = sessionId ?? flowId;
      // Add placeholder user message immediately
      addUserMessage({
        id: null,
        flow_id: currentFlowId,
        session_id: actualSession,
        text: inputValue,
        sender: "User",
        sender_name: "User",
        timestamp: new Date().toISOString(),
        files: files ?? [],
        edit: false,
        background_color: "",
        text_color: "",
      });

      await buildFlow({
        input_value: inputValue,
        startNodeId: chatInputId,
        files: files,
        silent: true,
        session: actualSession,
        eventDelivery: eventDeliveryConfig,
      })
        .then(() => {
          queryClient.invalidateQueries({
            queryKey: ["useGetSessionsFromFlowQuery"],
          });
        })
        .catch((err) => {
          console.error("[useSendMessage] buildFlow error", err);
          throw err;
        });
    },
    [
      buildFlow,
      chatInputId,
      sessionId,
      currentFlowId,
      eventDeliveryConfig,
      flowId,
    ],
  );

  return { sendMessage };
};
