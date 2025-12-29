import type { UseMutationResult } from "@tanstack/react-query";
import { refreshAllModelInputs } from "@/hooks/use-refresh-model-inputs";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteGlobalVariablesParams {
  id: string | undefined;
}

export const useDeleteGlobalVariables: useMutationFunctionType<
  undefined,
  DeleteGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteGlobalVariables = async ({
    id,
  }: DeleteGlobalVariablesParams): Promise<any> => {
    const res = await api.delete(`${getURL("VARIABLES")}/${id}`);
    return res.data;
  };

  const mutation: UseMutationResult<
    DeleteGlobalVariablesParams,
    any,
    DeleteGlobalVariablesParams
  > = mutate(["useDeleteGlobalVariables"], deleteGlobalVariables, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] });
      queryClient.refetchQueries({ queryKey: ["useGetModelProviders"] });
      refreshAllModelInputs(queryClient, { silent: true });
    },
    ...options,
  });

  return mutation;
};
