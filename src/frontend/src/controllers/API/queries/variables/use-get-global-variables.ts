import type { UseQueryResult } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import getUnavailableFields from "@/stores/globalVariablesStore/utils/get-unavailable-fields";
import type { useQueryFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { appendProviderScope } from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[],
  { flowId?: string; projectId?: string }
> = (options?) => {
  const { query } = UseRequestProcessor();

  const setGlobalVariablesEntries = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntries,
  );
  const setUnavailableFields = useGlobalVariablesStore(
    (state) => state.setUnavailableFields,
  );
  const setGlobalVariablesEntities = useGlobalVariablesStore(
    (state) => state.setGlobalVariablesEntities,
  );

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { flowId, projectId, ...queryOptions } = options ?? {};

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return [];
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    const res = await api.get(
      `${getURL("VARIABLES")}/${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
    );
    setGlobalVariablesEntries(res.data.map((entry) => entry.name));
    setUnavailableFields(getUnavailableFields(res.data));
    setGlobalVariablesEntities(res.data);
    return res.data;
  };

  const queryResult: UseQueryResult<GlobalVariable[], Error> = query(
    ["useGetGlobalVariables", flowId, projectId],
    getGlobalVariablesFn,
    {
      refetchOnWindowFocus: false,
      enabled: isAuthenticated && (options?.enabled ?? true),
      ...queryOptions,
    },
  );

  return queryResult;
};
