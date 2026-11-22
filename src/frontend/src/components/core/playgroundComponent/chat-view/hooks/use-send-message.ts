import { useCallback } from "react";
import { useShallow } from "zustand/react/shallow";
import { queryClient } from "@/contexts";
import { extractApiErrorMessage } from "@/controllers/API/helpers/extract-api-error-message";
import i18n from "@/i18n";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import { useGetFlowId } from "../../hooks/use-get-flow-id";
import {
  addUserMessage,
  removePlaceholderUserMessage,
  updateMessage,
} from "../utils/message-utils";

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
      const previousError = useAlertStore.getState().errorData;
      let messageAccepted = false;
      // Add placeholder user message immediately
      const placeholderId = addUserMessage({
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
        onUserMessage: (message) => {
          messageAccepted = true;
          updateMessage(message, placeholderId);
        },
      })
        .then(() => {
          const { buildInfo } = useFlowStore.getState();
          // The streaming bridge resolves failed requests. Reject an unsent message so
          // ChatInput restores its draft, while keeping messages the server accepted.
          if (
            buildInfo?.success === false &&
            buildInfo.error?.length &&
            !messageAccepted
          ) {
            throw new Error(
              buildInfo.error?.join("\n") || i18n.t("humanInput.runFailed"),
            );
          }
          if (messageAccepted) {
            removePlaceholderUserMessage(
              actualSession,
              currentFlowId,
              placeholderId,
            );
          }
          queryClient.invalidateQueries({
            queryKey: ["useGetSessionsFromFlowQuery"],
          });
        })
        .catch((err) => {
          console.error("[useSendMessage] buildFlow error", err);
          removePlaceholderUserMessage(
            actualSession,
            currentFlowId,
            placeholderId,
          );
          useFlowStore.getState().setIsBuilding(false);
          useUtilityStore.getState().setAwaitingBotResponse(false);
          const title = i18n.t("humanInput.runFailed");
          const message = extractApiErrorMessage(
            err && typeof err === "object" ? err : {},
            title,
          );
          const alerts = useAlertStore.getState();
          if (alerts.errorData === previousError) {
            alerts.setErrorData({ title, list: [message] });
          }
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
