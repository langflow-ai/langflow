import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentConfigItem {
  connection_id: string;
  app_id: string;
  type?: string;
}

export interface DeploymentConfigListResponse {
  configs: DeploymentConfigItem[];
  page: number;
  size: number;
  total: number;
}

interface DeploymentConfigListApiResponse {
  page?: number;
  size?: number;
  total?: number;
  provider_data?: {
    connections?: DeploymentConfigItem[];
    configs?: DeploymentConfigItem[];
    page?: number;
    size?: number;
    total?: number;
  } | null;
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
      const { data } = await api.get<DeploymentConfigListApiResponse>(
        `${getURL("DEPLOYMENTS")}/configs`,
        { params: { provider_id: providerId, size: 10000 } },
      );
      const providerData = data.provider_data;
      // Normalize provider-shaped list payloads into a stable FE shape.
      const providerConfigs =
        providerData?.connections ?? providerData?.configs ?? [];
      return {
        configs: providerConfigs,
        page: providerData?.page ?? data.page ?? 1,
        size: providerData?.size ?? data.size ?? providerConfigs.length,
        total: providerData?.total ?? data.total ?? providerConfigs.length,
      };
    };

  return query(
    ["useGetDeploymentConfigs", { providerId }],
    getDeploymentConfigsFn,
    options,
  );
};
