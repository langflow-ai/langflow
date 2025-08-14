import type { useMutationFunctionType } from "@/types/api";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface UseDeleteSessionParams {
  flowId?: string;
  useLocalStorage?: boolean;
}

interface DeleteSessionParams {
  sessionId: string;
}

export const useDeleteSession: useMutationFunctionType<
  UseDeleteSessionParams,
  DeleteSessionParams
> = ({ flowId, useLocalStorage }, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteSession = async ({
    sessionId,
  }: DeleteSessionParams): Promise<any> => {
    if (!flowId) {
      throw new Error("Flow ID is required");
    }

    if (useLocalStorage) {
      const messages = JSON.parse(sessionStorage.getItem(flowId) || "");
      const filteredMessages = messages.filter(
        (message: any) => message.session_id !== sessionId
      );
      sessionStorage.setItem(flowId, JSON.stringify(filteredMessages));
      return {
        data: filteredMessages,
      };
    } else {
      const response = await api.delete(
        `${getURL("MESSAGES")}/session/${sessionId}`
      );
      return response.data;
    }
  };

  const mutation: UseMutationResult<
    DeleteSessionParams,
    any,
    DeleteSessionParams
  > = mutate(["useDeleteSession"], deleteSession, {
    ...options,
    onSettled: (data, error, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery", { flowId }],
      });
      options?.onSettled?.(data, error, variables, context);
    },
  });

  return mutation;
};
