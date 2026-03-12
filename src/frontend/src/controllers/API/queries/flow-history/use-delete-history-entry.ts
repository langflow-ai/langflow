import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteHistoryEntry {
  flowId: string;
  historyId: string;
}

export const useDeleteHistoryEntry: useMutationFunctionType<
  undefined,
  IDeleteHistoryEntry
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteEntryFn = async (payload: IDeleteHistoryEntry): Promise<void> => {
    try {
      await api.delete(
        `${getURL("FLOWS")}/${payload.flowId}/history/${payload.historyId}`,
      );
    } catch {
      await api.delete(
        `${getURL("FLOWS")}/${payload.flowId}/versions/${payload.historyId}`,
      );
    }
  };

  const mutation: UseMutationResult<void, unknown, IDeleteHistoryEntry> =
    mutate(["useDeleteHistoryEntry"], deleteEntryFn, {
      ...options,
      onSettled: () => {
        queryClient.refetchQueries({
          queryKey: ["useGetFlowHistory"],
        });
      },
    });

  return mutation;
};
