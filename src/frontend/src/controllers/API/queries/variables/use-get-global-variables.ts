import type { UseQueryResult } from "@tanstack/react-query";
import useAuthStore from "@/stores/authStore";
import { useGlobalVariablesStore } from "@/stores/globalVariablesStore/globalVariables";
import type { useQueryFunctionType } from "@/types/api";
import type { GlobalVariable } from "@/types/global_variables";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { getGlobalVariablesQueryKey } from "../../helpers/global-variable-scope";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

interface GetGlobalVariablesOptions extends ProviderScopeParams {
  mirrorToStore?: boolean;
}

export { getGlobalVariablesQueryKey };

export const useGetGlobalVariables: useQueryFunctionType<
  undefined,
  GlobalVariable[],
  GetGlobalVariablesOptions
> = (options?) => {
  const { query } = UseRequestProcessor();

  const setGlobalVariables = useGlobalVariablesStore(
    (state) => state.setGlobalVariables,
  );

  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const {
    flowId,
    projectId,
    mirrorToStore = false,
    ...queryOptions
  } = options ?? {};

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return [];
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    const res = await api.get(
      `${getURL("VARIABLES")}/${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
    );
    if (mirrorToStore && !flowId && !projectId) {
      setGlobalVariables(res.data);
    }
    return res.data;
  };

  const queryResult: UseQueryResult<GlobalVariable[], Error> = query(
    getGlobalVariablesQueryKey({ flowId, projectId }),
    getGlobalVariablesFn,
    {
      refetchOnWindowFocus: false,
      enabled: isAuthenticated && (options?.enabled ?? true),
      ...queryOptions,
    },
  );

  return queryResult;
};
