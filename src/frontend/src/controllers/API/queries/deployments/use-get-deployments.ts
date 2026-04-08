import type { Deployment } from "@/pages/MainPage/pages/deploymentsPage/types";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentListResponse {
  deployments: Deployment[];
  page: number;
  size: number;
  total: number;
}

interface GetDeploymentsParams {
  provider_id: string;
  flow_ids?: string;
  page?: number;
  size?: number;
}

export const useGetDeployments: useQueryFunctionType<
  GetDeploymentsParams,
  DeploymentListResponse
> = ({ provider_id, flow_ids, page = 1, size = 20 }, options) => {
  const { query } = UseRequestProcessor();

  const getDeploymentsFn = async (): Promise<DeploymentListResponse> => {
    const { data } = await api.get<DeploymentListResponse>(
      `${getURL("DEPLOYMENTS")}`,
      { params: { provider_id, flow_ids, page, size } },
    );
    return data;
  };

  return query(
    ["useGetDeployments", { provider_id, flow_ids, page, size }],
    getDeploymentsFn,
    options,
  );
};
