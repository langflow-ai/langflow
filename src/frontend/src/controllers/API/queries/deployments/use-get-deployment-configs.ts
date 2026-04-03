import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentConfigItem {
  id: string;
  name: string;
  created_at: string | null;
  updated_at: string | null;
  provider_data: Record<string, unknown> | null;
}

export interface DeploymentConfigListResponse {
  configs: DeploymentConfigItem[];
  page: number;
  size: number;
  total: number;
}

interface GetDeploymentConfigsParams {
  providerId: string;
}

export const useGetDeploymentConfigs: useQueryFunctionType<
  GetDeploymentConfigsParams,
  DeploymentConfigListResponse
> = ({ providerId }, options) => {
  const { query } = UseRequestProcessor();

  const getDeploymentConfigsFn =
    async (): Promise<DeploymentConfigListResponse> => {
      const { data } = await api.get<DeploymentConfigListResponse>(
        `${getURL("DEPLOYMENTS")}/configs`,
        { params: { provider_id: providerId, size: 10000 } },
      );
      return data;
    };

  return query(
    ["useGetDeploymentConfigs", { providerId }],
    getDeploymentConfigsFn,
    options,
  );
};
