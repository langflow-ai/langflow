import type { UseMutationResult } from "@tanstack/react-query";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useFlowStore from "@/stores/flowStore";
import type { useMutationFunctionType } from "@/types/api";
import type { Message } from "@/types/messages";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

const MESSAGES_QUERY_KEY = "useGetMessagesQuery";

interface UpdateMessageParams {
  message: Partial<Message>;
  refetch?: boolean;
}

export const useUpdateMessage: useMutationFunctionType<
  undefined,
  UpdateMessageParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const flowId = useGetFlowId();

  const updateMessageApi = async (data: UpdateMessageParams) => {
    const isPlayground = useFlowStore.getState().playgroundPage;
    const message = data.message;
    if (message.files && typeof message.files === "string") {
      message.files = JSON.parse(message.files);
    }
    if (isPlayground && flowId) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "");
      const messageIndex = messages.findIndex(
        (m: Message) => m.id === message.id,
      );
      const existingMessage = messages[messageIndex];
      const textChanged =
        message.text !== undefined && message.text !== existingMessage.text;
      messages[messageIndex] = {
        ...existingMessage,
        ...message,
        flow_id: flowId,
        edit: textChanged ? true : existingMessage.edit,
      };
      sessionStorage.setItem(flowId, JSON.stringify(messages));
    } else {
      const result = await api.put(
        `${getURL("MESSAGES")}/${message.id}`,
        message,
      );
      return result.data;
    }
  };

  const mutation: UseMutationResult<Message, any, UpdateMessageParams> = mutate(
    ["useUpdateMessages"],
    updateMessageApi,
    {
      ...options,
      onSettled: (_, __, variables, ___) => {
        const params = variables as unknown as UpdateMessageParams | undefined;
        if (!flowId) return;

        const message = params?.message;
        const sessionId = message?.session_id;

        // Always update the session-specific cache so UI reflects the change
        if (sessionId && message) {
          const sessionCacheKey = [
            MESSAGES_QUERY_KEY,
            { id: flowId, session_id: sessionId },
          ];
          queryClient.setQueryData(sessionCacheKey, (old: Message[] = []) => {
            let existingIndex = old.findIndex((m) => m.id === message.id);
            // Handle placeholder messages whose id is still null
            // (chatHistory maps null → "" so message.id arrives as "")
            if (existingIndex === -1 && !message.id) {
              existingIndex = old.findIndex(
                (m) => m.id === null && m.sender === message.sender,
              );
            }
            if (existingIndex !== -1) {
              return old.map((m, idx) => {
                if (idx !== existingIndex) return m;
                const textChanged =
                  message.text !== undefined && message.text !== m.text;
                return {
                  ...m,
                  text: message.text,
                  edit: textChanged ? true : m.edit,
                  properties: message.properties ?? m.properties,
                };
              });
            }
            return old;
          });
        }

        // Only refetch the main query when explicitly requested (text edits)
        if (params?.refetch) {
          queryClient.refetchQueries({
            queryKey: [MESSAGES_QUERY_KEY, { id: flowId }],
            exact: true,
          });
        }
      },
    },
  );

  return mutation;
};
