import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchGlobalVariablesParams {
  name?: string;
  value?: string;
  id: string;
  default_fields?: string[];
}

export const usePatchGlobalVariables: useMutationFunctionType<
  undefined,
  PatchGlobalVariablesParams
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchGlobalVariables(
    GlobalVariable: PatchGlobalVariablesParams,
  ): Promise<any> {
    const res = await api.patch(
      `${getURL("VARIABLES")}/${GlobalVariable.id}`,
      GlobalVariable,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    PatchGlobalVariablesParams,
    any,
    PatchGlobalVariablesParams
  > = mutate(["usePatchGlobalVariables"], patchGlobalVariables, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetGlobalVariables"] });
    },
    ...options,
    retry: false,
  });

  return mutation;
};
