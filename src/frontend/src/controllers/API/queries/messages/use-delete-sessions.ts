import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteSessionParams {
  sessionId: string;
  flowId?: string;
}

export const useDeleteSession = (options?: {
  onSuccess?: (data: any, variables: DeleteSessionParams) => void;
  onSettled?: (data: any, error: any, variables: DeleteSessionParams) => void;
  onError?: (error: any) => void;
}) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteSession = async ({
    sessionId,
  }: DeleteSessionParams): Promise<any> => {
    const response = await api.delete(
      `${getURL("MESSAGES")}/session/${sessionId}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<any, any, DeleteSessionParams> = mutate(
    ["useDeleteSession"],
    deleteSession,
    {
      ...options,
      onSuccess: (data, variables) => {
        const vars = variables as unknown as DeleteSessionParams;
        // Remove all message queries for this session immediately
        if (vars.flowId) {
          // Remove session-specific queries
          queryClient.removeQueries({
            queryKey: [
              "useGetMessagesQuery",
              { id: vars.flowId, session_id: vars.sessionId },
            ],
          });

          // Also remove any queries that might have the session_id in params
          queryClient.removeQueries({
            predicate: (query) => {
              const queryKey = query.queryKey;
              if (
                Array.isArray(queryKey) &&
                queryKey[0] === "useGetMessagesQuery"
              ) {
                const params = queryKey[1] as Record<string, any>;
                if (params?.params?.session_id === vars.sessionId) {
                  return true;
                }
              }
              return false;
            },
          });
        }
        options?.onSuccess?.(data, vars);
      },
      onSettled: (data, error, variables) => {
        const vars = variables as unknown as DeleteSessionParams;
        // Invalidate sessions list to refresh the sidebar
        queryClient.invalidateQueries({
          queryKey: ["useGetSessionsFromFlowQuery"],
        });

        // Invalidate all message queries to ensure fresh data everywhere
        if (vars.flowId) {
          queryClient.invalidateQueries({
            queryKey: ["useGetMessagesQuery"],
            refetchType: "none", // Prevent automatic refetching
          });
        }

        options?.onSettled?.(data, error, vars);
      },
    },
  );

  return mutation;
};
