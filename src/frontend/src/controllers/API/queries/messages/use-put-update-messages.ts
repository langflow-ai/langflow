import { useMutationFunctionType } from "@/types/api";
import { Message } from "@/types/messages";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UpdateMessageParams {
  message: Message;
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
    const result = await api.put(`${getURL("MESSAGES")}/${message.id}`, data);
    return result.data;
  };

  const mutation: UseMutationResult<
    Message,
    any,
    UpdateMessageParams
  > = mutate(["useUpdateMessages"], updateMessageApi, {
    ...options,
    onSettled: (_, __, params, ___) => {
      //@ts-ignore
      if (params?.refetch) {
        queryClient.refetchQueries({
          queryKey: ["useGetMessagesQuery"],
          exact: false,
        });
      }
    },
  });

  return mutation;
};
