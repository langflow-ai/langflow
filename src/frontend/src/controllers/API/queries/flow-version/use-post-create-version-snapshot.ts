import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowVersionCreate, FlowVersionEntry } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ICreateVersionSnapshot {
  flowId: string;
  description?: string | null;
}

export const usePostCreateVersionSnapshot: useMutationFunctionType<
  undefined,
  ICreateVersionSnapshot
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createSnapshotFn = async (
    payload: ICreateVersionSnapshot,
  ): Promise<FlowVersionEntry> => {
    const body: FlowVersionCreate = { description: payload.description };
    const response = await api.post<FlowVersionEntry>(
      `${getURL("FLOWS")}/${payload.flowId}/versions/`,
      body,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowVersionEntry,
    unknown,
    ICreateVersionSnapshot
  > = mutate(["usePostCreateVersionSnapshot"], createSnapshotFn, {
    ...options,
    onSettled: (_, __, variables) => {
      queryClient.refetchQueries({
        queryKey: ["useGetFlowVersions", { flowId: variables?.flowId }],
      });
    },
  });

  return mutation;
};
