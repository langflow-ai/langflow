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
    const response = await api.post<FlowHistoryEntry>(
      `${getURL("FLOWS")}/${payload.flowId}/history/`,
      body,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowHistoryEntry,
    any,
    ICreateSnapshot
  > = mutate(["usePostCreateSnapshot"], createSnapshotFn, {
    ...options,
    onSettled: (_, __, variables) => {
      queryClient.refetchQueries({
        queryKey: ["useGetFlowHistory", { flowId: variables?.flowId }],
      });
    },
  });

  return mutation;
};
