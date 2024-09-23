import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useMutationFunctionType } from "@/types/api";
import { Message } from "@/types/messages";
import { UseMutationResult } from "@tanstack/react-query";
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
    const message = data.message;
    if (message.files && typeof message.files === "string") {
      message.files = JSON.parse(message.files);
    }
    const result = await api.put(
      `${getURL("MESSAGES")}/${message.id}`,
      message,
    );
    return result.data;
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
