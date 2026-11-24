import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BulkDeleteSessionsParams {
  sessionIds: string[];
}

// The bulk delete endpoint rejects larger requests.
const MAX_SESSIONS_PER_REQUEST = 500;

export const useBulkDeleteSessions: useMutationFunctionType<
  undefined,
  BulkDeleteSessionsParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const bulkDeleteSessions = async ({
    sessionIds,
  }: BulkDeleteSessionsParams): Promise<void> => {
    // "Select all" covers every loaded page, which can exceed one request.
    for (
      let start = 0;
      start < sessionIds.length;
      start += MAX_SESSIONS_PER_REQUEST
    ) {
      await api.delete(`${getURL("MESSAGES")}/sessions`, {
        data: sessionIds.slice(start, start + MAX_SESSIONS_PER_REQUEST),
      });
    }
  };

  const mutation: UseMutationResult<void, Error, BulkDeleteSessionsParams> =
    mutate(["useBulkDeleteSessions"], bulkDeleteSessions, {
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
