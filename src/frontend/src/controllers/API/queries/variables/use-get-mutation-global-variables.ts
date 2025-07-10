import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import type { useMutationFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariablesMutation: useMutationFunctionType<
  undefined
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  );
  const setUnavailableFields = useGlobalVariablesStore(
    (state) => state.setUnavailableFields,
  );

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    const res = await api.get(`${getURL("VARIABLES")}/`);
    setGlobalVariablesEntries(res.data.map((entry) => entry.name));
    setUnavailableFields(getUnavailableFields(res.data));
    return res.data;
  };

  const mutation: UseMutationResult<undefined, Error, GlobalVariable[]> =
    mutate(["useGetGlobalVariables"], getGlobalVariablesFn, options);

  return mutation;
};
