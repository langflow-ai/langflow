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
      messages[messageIndex] = {
        ...messages[messageIndex],
        ...message,
        flow_id: flowId,
        edit: true,
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
        if (params?.refetch && flowId) {
          const message = params.message;
          const sessionId = message.session_id;

          // Update the session-specific cache directly so UI updates
          if (sessionId) {
            const sessionCacheKey = [
              MESSAGES_QUERY_KEY,
              { id: flowId, session_id: sessionId },
            ];
            queryClient.setQueryData(sessionCacheKey, (old: Message[] = []) => {
              const existingIndex = old.findIndex((m) => m.id === message.id);
              if (existingIndex !== -1) {
                // Update existing message with new text and mark as edited
                return old.map((m, idx) =>
                  idx === existingIndex
                    ? { ...m, text: message.text, edit: true }
                    : m,
                );
              }
              return old;
            });
          }

          // Also refetch the main query for backend sync
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
