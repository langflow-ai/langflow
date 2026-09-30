import { useQueryFunctionType } from "@/types/api";
import type { ModelType } from "@/types/models";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
  providerScopeQueryKey,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

export interface EnabledModelsResponse {
  enabled_models: Record<string, Record<string, boolean>>;
  /**
   * Type-aware status map. Older servers omit this field; callers must only
   * fall back to enabled_models when the selected provider has no typed map.
   */
  enabled_models_by_type?: Record<
    string,
    Partial<Record<ModelType, Record<string, boolean>>>
  >;
}

export interface EnabledModelsQueryParams extends ProviderScopeParams {
  purpose?: "use" | "configure";
}

export const getEnabledModelsQueryKey = (params?: EnabledModelsQueryParams) =>
  params?.flowId || params?.projectId || params?.purpose
    ? ([
        "useGetEnabledModels",
        ...providerScopeQueryKey(params),
        params?.purpose,
      ] as const)
    : (["useGetEnabledModels"] as const);

export const useGetEnabledModels: useQueryFunctionType<
  undefined,
  EnabledModelsResponse,
  EnabledModelsQueryParams
> = (options) => {
  const { query } = UseRequestProcessor();
  const { flowId, projectId, purpose, ...queryOptions } = options ?? {};
  const params = { flowId, projectId, purpose };

  const getEnabledModelsFn = async (): Promise<EnabledModelsResponse> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, params);
    if (purpose) queryParams.set("purpose", purpose);
    const response = await api.get<EnabledModelsResponse>(
      `${getURL("MODELS")}/enabled_models${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
    );
    return response.data;
  };

  const queryResult = query(
    getEnabledModelsQueryKey(params),
    getEnabledModelsFn,
    Object.keys(queryOptions).length > 0 ? queryOptions : undefined,
  );

  return queryResult;
};
