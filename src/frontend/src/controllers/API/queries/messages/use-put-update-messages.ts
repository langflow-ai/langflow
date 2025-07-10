import type { UseMutationResult } from "@tanstack/react-query";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { useMutationFunctionType } from "@/types/api";
import type { Message } from "@/types/messages";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateMessageParams {
  message: Partial<Message>;
  refetch?: boolean;
}

export const useUpdateMessage: useMutationFunctionType<
  undefined,
  UpdateMessageParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateMessageApi = async (data: UpdateMessageParams) => {
    const isPlayground = useFlowStore.getState().playgroundPage;
    const flowId = useFlowsManagerStore.getState().currentFlowId;
    const message = data.message;
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

  const mutation: UseMutationResult<Message, any, UpdateMessageParams> = mutate(
    ["useUpdateMessages"],
    updateMessageApi,
    {
      ...options,
      onSettled: (_, __, params, ___) => {
        const flowId = useFlowsManagerStore.getState().currentFlowId;
        //@ts-ignore
        if (params?.refetch && flowId) {
          queryClient.refetchQueries({
            queryKey: ["useGetMessagesQuery", { id: flowId }],
            exact: true,
          });
        }
      },
    },
  );

  return mutation;
};
