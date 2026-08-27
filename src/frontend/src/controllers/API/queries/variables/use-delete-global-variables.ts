import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";
import { getGlobalVariablesQueryKey } from "./use-get-global-variables";

interface DeleteGlobalVariablesParams extends ProviderScopeParams {
  id: string | undefined;
}

export const useDeleteGlobalVariables: useMutationFunctionType<
  undefined,
  DeleteGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteGlobalVariables = async ({
    id,
    flowId,
    projectId,
  }: DeleteGlobalVariablesParams): Promise<void> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    await api.delete(
      `${getURL("VARIABLES")}/${id}${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
    );
  };

  const mutation: UseMutationResult<
    void,
    unknown,
    DeleteGlobalVariablesParams
  > = mutate(["useDeleteGlobalVariables"], deleteGlobalVariables, {
    onSettled: (data, error, variables) => {
      queryClient.refetchQueries({
        queryKey: getGlobalVariablesQueryKey(variables),
        exact: true,
      });
    },
    ...options,
  });

  return mutation;
};
