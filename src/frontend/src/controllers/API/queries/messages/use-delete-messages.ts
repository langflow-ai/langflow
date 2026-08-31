import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMessagesParams {
  ids: string[];
}

export const useDeleteMessages: useMutationFunctionType<
  undefined,
  DeleteMessagesParams,
  DeleteMessagesParams,
  Error
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteMessage = async ({
    ids,
  }: DeleteMessagesParams): Promise<DeleteMessagesParams> => {
    const response = await api.delete<DeleteMessagesParams>(
      `${getURL("MESSAGES")}`,
      {
        data: ids,
      },
    );

    return response.data;
  };

  const mutation: UseMutationResult<
    DeleteMessagesParams,
    Error,
    DeleteMessagesParams
  > = mutate(["useDeleteMessages"], deleteMessage, {
    ...options,
    onSettled: (...args) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });
      options?.onSettled?.(...args);
    },
  });

  return mutation;
};
