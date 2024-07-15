import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import { Message } from "@/types/messages";

interface UpdateMessageParams {
  message: Message;
}

export const useUpdateMessages: useMutationFunctionType<
  UpdateMessageParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const updateMessageApi = async (data: Message) => {
    if (data.files && typeof data.files === "string") {
      data.files = JSON.parse(data.files);
    }
    const result =  await api.put(`${getURL("MESSAGES")}/${data.id}`, data);
    return result.data;
  }

  const mutation: UseMutationResult<
    UpdateMessageParams,
    any,
    UpdateMessageParams
  > = mutate(["useUpdateMessages",], updateMessageApi, options);

  return mutation;
};
