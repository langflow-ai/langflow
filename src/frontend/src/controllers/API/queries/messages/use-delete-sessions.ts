import type { UseMutationResult } from "@tanstack/react-query";
import type {
  DeleteSessionError,
  DeleteSessionParams,
  DeleteSessionResponse,
} from "@/types/messages/session";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteSession = (options?: {
  onSuccess?: (
    data: DeleteSessionResponse,
    variables: DeleteSessionParams,
    context: unknown,
  ) => void;
  onSettled?: (
    data: DeleteSessionResponse | undefined,
    error: DeleteSessionError | null,
    variables: DeleteSessionParams,
    context: unknown,
  ) => void;
  onError?: (error: DeleteSessionError) => void;
}) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteSession = async ({
    sessionId,
  }: DeleteSessionParams): Promise<DeleteSessionResponse> => {
    const response = await api.delete(
      `${getURL("MESSAGES")}/session/${sessionId}`,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    DeleteSessionResponse,
    DeleteSessionError,
    DeleteSessionParams
  > = mutate(["useDeleteSession"], deleteSession, {
    ...options,
    onSuccess: (data, variables, context, ...rest) => {
      // Cast needed because UseRequestProcessor's mutate doesn't properly infer callback types
      const vars = variables as unknown as DeleteSessionParams;

      // Remove all message queries for this session immediately to prevent stale data
      if (vars.flowId) {
        // Remove session-specific queries
        queryClient.removeQueries({
          queryKey: [
            "useGetMessagesQuery",
            { id: vars.flowId, session_id: vars.sessionId },
          ],
        });

        // Also remove any queries that might have the session_id in params (e.g., Message Logs)
        queryClient.removeQueries({
          predicate: (query) => {
            const queryKey = query.queryKey;
            if (
              Array.isArray(queryKey) &&
              queryKey[0] === "useGetMessagesQuery"
            ) {
              const params = queryKey[1] as Record<string, unknown>;
              if (params?.params && typeof params.params === "object") {
                const nestedParams = params.params as Record<string, unknown>;
                if (nestedParams.session_id === vars.sessionId) {
                  return true;
                }
              }
            }
            return false;
          },
        });
      }
      options?.onSuccess?.(data, vars, context);
    },
    onSettled: (data, error, variables, context, ...rest) => {
      // Cast needed because UseRequestProcessor's mutate doesn't properly infer callback types
      const vars = variables as unknown as DeleteSessionParams;

      // Invalidate sessions list to refresh the sidebar
      queryClient.invalidateQueries({
        queryKey: ["useGetSessionsFromFlowQuery"],
      });

      // Invalidate all message queries to ensure fresh data everywhere
      if (vars.flowId) {
        queryClient.invalidateQueries({
          queryKey: ["useGetMessagesQuery"],
          refetchType: "none", // Prevent automatic refetching to avoid race conditions
        });
      }

      options?.onSettled?.(data, error, vars, context);
    },
  });

  return mutation;
};
