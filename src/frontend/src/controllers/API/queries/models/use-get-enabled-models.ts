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

export const getEnabledModelsQueryKey = (params?: ProviderScopeParams) =>
  params?.flowId || params?.projectId
    ? (["useGetEnabledModels", ...providerScopeQueryKey(params)] as const)
    : (["useGetEnabledModels"] as const);

export const useGetEnabledModels: useQueryFunctionType<
  undefined,
  EnabledModelsResponse,
  ProviderScopeParams
> = (options) => {
  const { query } = UseRequestProcessor();
  const { flowId, projectId, ...queryOptions } = options ?? {};
  const params = { flowId, projectId };

  const getEnabledModelsFn = async (): Promise<EnabledModelsResponse> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, params);
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
