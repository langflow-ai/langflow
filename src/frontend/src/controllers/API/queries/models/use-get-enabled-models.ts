import { useQueryFunctionType } from "@/types/api";
import type { ModelType } from "@/types/models";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
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

export const useGetEnabledModels: useQueryFunctionType<
  undefined,
  EnabledModelsResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const getEnabledModelsFn = async (): Promise<EnabledModelsResponse> => {
    const response = await api.get<EnabledModelsResponse>(
      `${getURL("MODELS")}/enabled_models`,
    );
    return response.data;
  };

  const queryResult = query(
    ["useGetEnabledModels"],
    getEnabledModelsFn,
    options,
  );

  return queryResult;
};
