import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import { useQueryFunctionType } from "@/types/api";
import { GlobalVariable } from "@/types/global_variables";
import { UseQueryResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  );
  const setUnavailableFields = useGlobalVariablesStore(
    (state) => state.setUnavailableFields,
  );

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return [];
    const res = await api.get(`${getURL("VARIABLES")}/`);
    setGlobalVariablesEntries(res.data.map((entry) => entry.name));
    setUnavailableFields(getUnavailableFields(res.data));
    return res.data;
  };

  const queryResult: UseQueryResult<GlobalVariable[], any> = query(
    ["useGetGlobalVariables"],
    getGlobalVariablesFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
