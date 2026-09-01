import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";
import { getGlobalVariablesQueryKey } from "./use-get-global-variables";

interface PatchGlobalVariablesParams extends ProviderScopeParams {
  name?: string;
  value?: string;
  id: string;
  default_fields?: string[];
  category?: string;
}

export const usePatchGlobalVariables: useMutationFunctionType<
  undefined,
  PatchGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchGlobalVariables(
    globalVariable: PatchGlobalVariablesParams,
  ): Promise<GlobalVariable> {
    const { flowId, projectId, ...body } = globalVariable;
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    const res = await api.patch(
      `${getURL("VARIABLES")}/${globalVariable.id}${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
      body,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    GlobalVariable,
    unknown,
    PatchGlobalVariablesParams
  > = mutate(["usePatchGlobalVariables"], patchGlobalVariables, {
    onSettled: (data, error, variables) => {
      queryClient.refetchQueries({
        queryKey: getGlobalVariablesQueryKey(variables),
        exact: true,
      });
    },
    ...options,
    retry: false,
  });

  return mutation;
};
