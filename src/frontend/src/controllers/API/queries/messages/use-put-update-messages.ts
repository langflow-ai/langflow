import type { UseMutationResult } from "@tanstack/react-query";
import { useGetFlowId } from "@/modals/IOModal/hooks/useGetFlowId";
import useFlowStore from "@/stores/flowStore";
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
      onSettled: (_, __, params, ___) => {
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
