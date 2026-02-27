import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IDeleteVersionEntry {
  flowId: string;
  versionId: string;
}

export const useDeleteVersionEntry: useMutationFunctionType<
  undefined,
  IDeleteVersionEntry
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteEntryFn = async (payload: IDeleteVersionEntry): Promise<void> => {
    await api.delete(
      `${getURL("FLOWS")}/${payload.flowId}/versions/${payload.versionId}`,
    );
  };

  const mutation: UseMutationResult<void, any, IDeleteVersionEntry> = mutate(
    ["useDeleteVersionEntry"],
    deleteEntryFn,
    {
      ...options,
      onSettled: (_, __, variables) => {
        queryClient.refetchQueries({
          queryKey: ["useGetFlowVersions", { flowId: variables?.flowId }],
        });
      },
    },
  );

  return mutation;
};
