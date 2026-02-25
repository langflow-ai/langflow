import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface BulkDeleteSessionsParams {
  sessionIds: string[];
}

export const useBulkDeleteSessions: useMutationFunctionType<
  undefined,
  BulkDeleteSessionsParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const bulkDeleteSessions = async ({
    sessionIds,
  }: BulkDeleteSessionsParams): Promise<any> => {
    // Delete sessions one by one
    const deletePromises = sessionIds.map((sessionId) =>
      api.delete(`${getURL("MESSAGES")}/session/${sessionId}`)
    );
    
    await Promise.all(deletePromises);
    return { deleted: sessionIds.length };
  };

  const mutation: UseMutationResult<
    any,
    any,
    BulkDeleteSessionsParams
  > = mutate(["useBulkDeleteSessions"], bulkDeleteSessions, {
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
