import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface EnabledModelsResponse {
  enabled_models: Record<string, Record<string, boolean>>;
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
