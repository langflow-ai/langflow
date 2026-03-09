import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteFlowVersionEntry {
  flowId: string;
  versionId: string;
}

export const useDeleteFlowVersionEntry: useMutationFunctionType<
  undefined,
  IDeleteFlowVersionEntry
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteEntryFn = async (
    payload: IDeleteFlowVersionEntry,
  ): Promise<void> => {
    await api.delete(
      `${getURL("FLOWS")}/${payload.flowId}/versions/${payload.versionId}`,
    );
  };

  const mutation: UseMutationResult<void, unknown, IDeleteFlowVersionEntry> =
    mutate(["useDeleteFlowVersionEntry"], deleteEntryFn, {
      ...options,
      onSettled: (_, __, variables) => {
        queryClient.refetchQueries({
          queryKey: ["useGetFlowVersions", { flowId: variables?.flowId }],
        });
      },
    });

  return mutation;
};
