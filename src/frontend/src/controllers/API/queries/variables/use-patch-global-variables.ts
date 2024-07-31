import { changeUser, useMutationFunctionType } from "@/types/api";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchGlobalVariablesParams {
  name: string;
  value: string;
  id: string;
}

export const usePatchGlobalVariables: useMutationFunctionType<
  undefined,
  PatchGlobalVariablesParams
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  async function patchGlobalVariables({
    name,
    value,
    id,
  }: PatchGlobalVariablesParams): Promise<any> {
    const res = await api.patch(`${getURL("VARIABLES")}/${id}`, {
      name,
      value,
    });
    return res.data;
  }

  const mutation: UseMutationResult<
    PatchGlobalVariablesParams,
    any,
    PatchGlobalVariablesParams
  > = mutate(["usePatchGlobalVariables"], patchGlobalVariables, options);

  return mutation;
};
