import { UseMutationResult } from "@tanstack/react-query";
import { useMutationFunctionType } from "@/types/api";
import type { ModelType } from "@/types/models";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import {
  appendProviderScope,
  type ProviderScopeParams,
} from "../../helpers/provider-scope";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelStatusUpdate {
  provider: string;
  model_id: string;
  model_type: ModelType;
  enabled: boolean;
}

export interface UpdateEnabledModelsResponse {
  disabled_models: string[];
}

export const useUpdateEnabledModels: useMutationFunctionType<
  undefined,
  { updates: ModelStatusUpdate[] } & ProviderScopeParams,
  UpdateEnabledModelsResponse,
  Error
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const updateEnabledModelsFn = async ({
    updates,
    flowId,
    projectId,
  }: {
    updates: ModelStatusUpdate[];
  } & ProviderScopeParams): Promise<UpdateEnabledModelsResponse> => {
    const queryParams = new URLSearchParams();
    appendProviderScope(queryParams, { flowId, projectId });
    const response = await api.post<UpdateEnabledModelsResponse>(
      `${getURL("MODELS")}/enabled_models${
        queryParams.toString() ? `?${queryParams.toString()}` : ""
      }`,
      updates,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    UpdateEnabledModelsResponse,
    Error,
    { updates: ModelStatusUpdate[] } & ProviderScopeParams
  > = mutate(["useUpdateEnabledModels"], updateEnabledModelsFn, options);

  return mutation;
};
