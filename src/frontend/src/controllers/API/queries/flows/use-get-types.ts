import { useLayoutEffect } from "react";
import { ENABLE_KNOWLEDGE_BASES } from "@/customization/feature-flags";
import {
  recomputeComponentsToUpdateIfNeeded,
  syncNodeTranslations,
} from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
import type {
  APIObjectType,
  ComponentDisplayNamesType,
  useQueryFunctionType,
} from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  providerScopeStoreKey,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

const displayNamesByPalette = new WeakMap<
  APIObjectType,
  ComponentDisplayNamesType
>();

export const useGetTypes: useQueryFunctionType<
  undefined,
  APIObjectType,
  { checkCache?: boolean; flowId?: string; projectId?: string }
> = (options) => {
  const { query } = UseRequestProcessor();
  const setLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const activateScope = useTypesStore((state) => state.activateScope);
  const setScopedTypes = useTypesStore((state) => state.setScopedTypes);
  const {
    flowId,
    projectId,
    checkCache: _checkCache,
    ...queryOptions
  } = options ?? {};
  const scopeKey = providerScopeStoreKey({ flowId, projectId });

  const getTypesFn = async () => {
    try {
      const queryParams = new URLSearchParams({ force_refresh: "true" });
      appendProviderScope(queryParams, { flowId, projectId });
      const response = await api.get<APIObjectType>(
        `${getURL("ALL")}?${queryParams.toString()}`,
      );
      const raw = response?.data as Record<string, unknown>;

      const componentDisplayNames = raw?.component_display_names as
        | ComponentDisplayNamesType
        | undefined;
      delete raw.component_display_names;
      const data = raw as APIObjectType;

      if (!ENABLE_KNOWLEDGE_BASES) {
        delete data.knowledge_bases;
      }

      displayNamesByPalette.set(data, componentDisplayNames ?? {});
      return data;
    } catch (error) {
      console.error("[Types] Error fetching types:", error);
      setLoading(false);
      throw error;
    }
  };

  const queryResult = query(["useGetTypes", flowId, projectId], getTypesFn, {
    refetchOnWindowFocus: false,
    staleTime: Number.POSITIVE_INFINITY,
    ...queryOptions,
  });

  useLayoutEffect(() => {
    activateScope(scopeKey);
    if (
      queryResult.data &&
      setScopedTypes(
        scopeKey,
        queryResult.data,
        displayNamesByPalette.get(queryResult.data) ?? {},
      )
    ) {
      syncNodeTranslations();
      recomputeComponentsToUpdateIfNeeded();
    }
  }, [activateScope, queryResult.data, scopeKey, setScopedTypes]);

  return queryResult;
};
