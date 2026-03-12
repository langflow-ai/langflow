import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowHistoryCreate, FlowHistoryEntry } from "@/types/flow/history";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ICreateSnapshot {
  flowId: string;
  description?: string | null;
}

export const usePostCreateSnapshot: useMutationFunctionType<
  undefined,
  ICreateSnapshot
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createSnapshotFn = async (
    payload: ICreateSnapshot,
  ): Promise<FlowHistoryEntry> => {
    const body: FlowHistoryCreate = { description: payload.description };
    try {
      const response = await api.post<FlowHistoryEntry>(
        `${getURL("FLOWS")}/${payload.flowId}/history/`,
        body,
      );
      return response.data;
    } catch {
      const response = await api.post<FlowHistoryEntry>(
        `${getURL("FLOWS")}/${payload.flowId}/versions/`,
        body,
      );
      return response.data;
    }
  };

  const mutation: UseMutationResult<
    FlowHistoryEntry,
    unknown,
    ICreateSnapshot
  > = mutate(["usePostCreateSnapshot"], createSnapshotFn, {
    ...options,
    onSettled: () => {
      queryClient.refetchQueries({
        queryKey: ["useGetFlowHistory"],
      });
    },
  });

  return mutation;
};
