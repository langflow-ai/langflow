import { useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMessagesParams {
  ids: string[];
}

export const useDeleteMessages: useMutationFunctionType<
  undefined,
  DeleteMessagesParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const deleteMessage = async ({ ids }: DeleteMessagesParams): Promise<any> => {
    const response = await api.delete(`${getURL("MESSAGES")}`, {
      data: ids,
    });

    return response.data;
  };

  const mutation: UseMutationResult<
    DeleteMessagesParams,
    any,
    DeleteMessagesParams
  > = mutate(["useDeleteMessages"], deleteMessage, options);

  return mutation;
};
