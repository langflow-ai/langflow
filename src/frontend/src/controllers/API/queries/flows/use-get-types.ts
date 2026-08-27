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
import { appendProviderScope } from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

export const useGetTypes: useQueryFunctionType<
  undefined,
  APIObjectType,
  { checkCache?: boolean; flowId?: string; projectId?: string }
> = (options) => {
  const { query } = UseRequestProcessor();
  const setLoading = useFlowsManagerStore((state) => state.setIsLoading);
  const setTypes = useTypesStore((state) => state.setTypes);
  const setComponentDisplayNames = useTypesStore(
    (state) => state.setComponentDisplayNames,
  );
  const { flowId, projectId, ...queryOptions } = options ?? {};

  const getTypesFn = async (checkCache = false) => {
    try {
      if (checkCache) {
        const data = useTypesStore.getState().types;
        if (data && Object.keys(data).length > 0) {
          return data;
        }
      }

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

      if (componentDisplayNames) {
        setComponentDisplayNames(componentDisplayNames);
      }
      setTypes(data);
      syncNodeTranslations();
      recomputeComponentsToUpdateIfNeeded();
      return data;
    } catch (error) {
      console.error("[Types] Error fetching types:", error);
      setLoading(false);
      throw error;
    }
  };

  const queryResult = query(
    ["useGetTypes", flowId, projectId],
    () => getTypesFn(options?.checkCache),
    {
      refetchOnWindowFocus: false,
      ...queryOptions,
    },
  );

  return queryResult;
};
