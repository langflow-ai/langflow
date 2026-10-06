import type { UseMutationResult } from "@tanstack/react-query";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import type { useMutationFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariablesMutation: useMutationFunctionType<
  undefined
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const setGlobalVariables = useGlobalVariablesStore(
    (state) => state.setGlobalVariables,
  );

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    const res = await api.get(`${getURL("VARIABLES")}/`);
    setGlobalVariables(res.data);
    return res.data;
  };

  const mutation: UseMutationResult<undefined, Error, GlobalVariable[]> =
    mutate(["useGetGlobalVariables"], getGlobalVariablesFn, options);

  return mutation;
};
