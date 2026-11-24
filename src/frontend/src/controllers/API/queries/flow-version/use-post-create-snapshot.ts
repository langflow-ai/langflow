import type { UseMutationResult } from "@tanstack/react-query";
import type { AxiosError } from "axios";
import type { useMutationFunctionType } from "@/types/api";
import type { FlowVersionCreate, FlowVersionEntry } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface ICreateSnapshot {
  flowId: string;
  description?: string | null;
  /** The graph to archive. Omitted, the server snapshots what it already has. */
  data?: Record<string, unknown> | null;
}

export const usePostCreateSnapshot: useMutationFunctionType<
  undefined,
  ICreateSnapshot
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createSnapshotFn = async (
    payload: ICreateSnapshot,
  ): Promise<FlowVersionEntry> => {
    const body: FlowVersionCreate = {
      description: payload.description,
      data: payload.data,
    };
    const response = await api.post<FlowVersionEntry>(
      `${getURL("FLOWS")}/${payload.flowId}/versions/`,
      body,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    FlowVersionEntry,
    AxiosError,
    ICreateSnapshot
  > = mutate(["usePostCreateSnapshot"], createSnapshotFn, {
    ...options,
    onSettled: (_, __, variables) => {
      queryClient.refetchQueries({
        queryKey: ["useGetFlowVersions", { flowId: variables?.flowId }],
      });
    },
  });

  return mutation;
};
