import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentLlmListResponse {
  provider_data: {
    models: Array<{ model_name: string }>;
  } | null;
}

interface GetDeploymentLlmsParams {
  providerId: string;
}

export const useGetDeploymentLlms: useQueryFunctionType<
  GetDeploymentLlmsParams,
  DeploymentLlmListResponse
> = ({ providerId }, options) => {
  const { query } = UseRequestProcessor();

  const getDeploymentLlmsFn = async (): Promise<DeploymentLlmListResponse> => {
    const response = await api.get<DeploymentLlmListResponse>(
      `${getURL("DEPLOYMENTS")}/llms`,
      { params: { provider_id: providerId } },
    );
    if (!response) {
      throw new Error(
        "Failed to load models. Please check your provider credentials.",
      );
    }
    return response.data;
  };

  return query(["useGetDeploymentLlms", { providerId }], getDeploymentLlmsFn, {
    ...options,
    retry: false,
    staleTime: 1000 * 60 * 5,
  });
};
