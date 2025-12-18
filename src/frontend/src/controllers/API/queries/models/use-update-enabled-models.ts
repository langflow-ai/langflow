import { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseMutationResult } from "@tanstack/react-query";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ModelStatusUpdate {
  provider: string;
  model_id: string;
  enabled: boolean;
}

export interface UpdateEnabledModelsResponse {
  disabled_models: string[];
}

export const useUpdateEnabledModels: useMutationFunctionType<
  undefined,
  { updates: ModelStatusUpdate[] },
  UpdateEnabledModelsResponse,
  Error
> = (options?) => {
  const { mutate } = UseRequestProcessor();

  const updateEnabledModelsFn = async (data: {
    updates: ModelStatusUpdate[];
  }): Promise<UpdateEnabledModelsResponse> => {
    const response = await api.post<UpdateEnabledModelsResponse>(
      `${getURL("MODELS")}/enabled_models`,
      data.updates,
    );
    return response.data;
  };

  const mutation: UseMutationResult<
    UpdateEnabledModelsResponse,
    Error,
    { updates: ModelStatusUpdate[] }
  > = mutate(["useUpdateEnabledModels"], updateEnabledModelsFn, options);

  return mutation;
};
