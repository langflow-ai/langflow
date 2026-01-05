import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteSessionParams {
  sessionId: string;
}

export const useDeleteSession: useMutationFunctionType<
  undefined,
  DeleteSessionParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteSession = async ({
    sessionId,
  }: DeleteSessionParams): Promise<any> => {
    const response = await api.delete(
      `${getURL("MESSAGES")}/session/${sessionId}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    DeleteSessionParams,
    any,
    DeleteSessionParams
  > = mutate(["useDeleteSession"], deleteSession, {
    ...options,
    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });
      options?.onSettled?.(data, error, variables, context);
    },
  });

  return mutation;
};
