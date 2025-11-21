import { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DefaultModelResponse {
  default_model: {
    model_name: string;
    provider: string;
    model_type: string;
  } | null;
}

export const useGetDefaultModel: useQueryFunctionType<
  { model_type?: string } | undefined,
  DefaultModelResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getDefaultModelFn = async (): Promise<DefaultModelResponse> => {
    const modelType = params?.model_type || "language";
    const response = await api.get<DefaultModelResponse>(
      `${getURL("MODELS")}/default_model?model_type=${modelType}`,
    );
    return response.data;
  };

  const queryResult = query(
    ["useGetDefaultModel", params?.model_type],
    getDefaultModelFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 5, // 5 minutes
      ...options,
    },
  );

  return queryResult;
};
