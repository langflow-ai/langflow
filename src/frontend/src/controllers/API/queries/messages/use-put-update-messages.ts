import type { UseMutationResult } from "@tanstack/react-query";
import useFlowStore from "@/stores/flowStore";
import type { useMutationFunctionType } from "@/types/api";
import type { Message } from "@/types/messages";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateMessageParams {
  flowId: string;
  sessionId: string;
}

export const useUpdateMessage: useMutationFunctionType<
  UpdateMessageParams,
  Partial<Message>
> = ({ flowId, sessionId }, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateMessageApi = async (message: Partial<Message>) => {
    const isPlayground = useFlowStore.getState().playgroundPage;
    if (message.files && typeof message.files === "string") {
      message.files = JSON.parse(message.files);
    }
    if (isPlayground && flowId) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "");
      const messageIndex = messages.findIndex(
        (m: Message) => m.id === message.id,
      );
      messages[messageIndex] = message;
      sessionStorage.setItem(flowId, JSON.stringify(messages));
      return {
        data: message,
      };
    } else {
      const result = await api.put(
        `${getURL("MESSAGES")}/${message.id}`,
        message,
      );
      return result.data;
    }
  };

  const mutation: UseMutationResult<Message, any, Partial<Message>> = mutate(
    ["useUpdateMessages"],
    updateMessageApi,
    {
      ...options,
      onSettled: () => {
        queryClient.refetchQueries({
          queryKey: [
            "useGetMessagesQuery",
            { id: flowId, session_id: sessionId },
          ],
          exact: true,
        });
      },
    },
  );

  return mutation;
};
