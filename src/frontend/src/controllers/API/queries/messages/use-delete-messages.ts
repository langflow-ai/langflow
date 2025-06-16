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
  const { mutate, queryClient } = UseRequestProcessor();

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
  > = mutate(["useDeleteMessages"], deleteMessage, {
    ...options,
    onSettled: (data, error, variables, context) => {
      // Invalidate sessions query to refetch the updated session list
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });
      // Call the original onSettled if provided
      options?.onSettled?.(data, error, variables, context);
    },
  });

  return mutation;
};
