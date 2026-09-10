import type { UseQueryResult } from "@tanstack/react-query";
import { useEffect } from "react";
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

export const fetchGlobalVariables = async ({
  flowId,
  projectId,
}: ProviderScopeParams = {}): Promise<GlobalVariable[]> => {
  const queryParams = new URLSearchParams();
  appendProviderScope(queryParams, { flowId, projectId });
  const res = await api.get(
    `${getURL("VARIABLES")}/${
      queryParams.toString() ? `?${queryParams.toString()}` : ""
    }`,
  );
  return res.data;
};

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
  const isScoped = !!flowId || !!projectId;

  const getGlobalVariablesFn = async (): Promise<GlobalVariable[]> => {
    if (!isAuthenticated) return [];
    return fetchGlobalVariables({ flowId, projectId });
  };

  const queryResult: UseQueryResult<GlobalVariable[], Error> = query(
    getGlobalVariablesQueryKey({ flowId, projectId }),
    getGlobalVariablesFn,
    {
      ...queryOptions,
      // Scoped credentials are part of the active provider policy. Revalidate
      // them when focus returns so revocation does not wait for a remount. A
      // caller cannot disable that scoped safety refresh.
      refetchOnWindowFocus: isScoped
        ? true
        : (queryOptions.refetchOnWindowFocus ?? false),
      enabled: isAuthenticated && (queryOptions.enabled ?? true),
    },
  );

  useEffect(() => {
    if (
      mirrorToStore &&
      !flowId &&
      !projectId &&
      isAuthenticated &&
      queryResult.data !== undefined
    ) {
      setGlobalVariables(queryResult.data);
    }
  }, [
    flowId,
    isAuthenticated,
    mirrorToStore,
    projectId,
    queryResult.data,
    setGlobalVariables,
  ]);

  const shouldMaskScopedData =
    isScoped &&
    (queryResult.fetchStatus !== "idle" ||
      queryResult.isFetching ||
      queryResult.isError ||
      !queryResult.isSuccess);

  if (shouldMaskScopedData) {
    // React Query intentionally retains the last successful payload during a
    // refetch and after a refetch error. For scoped credentials that snapshot
    // can contain grants revoked since the last response, so callers must not
    // receive it until a new scoped request settles successfully.
    return {
      ...queryResult,
      data: undefined,
    } as UseQueryResult<GlobalVariable[], Error>;
  }

  return queryResult;
};
