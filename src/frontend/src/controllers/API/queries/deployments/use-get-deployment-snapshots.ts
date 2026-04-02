import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentSnapshotItem {
  id: string;
  name: string;
  provider_data: Record<string, unknown> | null;
}

export interface DeploymentSnapshotListResponse {
  snapshots: DeploymentSnapshotItem[];
  page: number;
  size: number;
  total: number;
}

interface GetDeploymentSnapshotsParams {
  providerId: string;
}

export const useGetDeploymentSnapshots: useQueryFunctionType<
  GetDeploymentSnapshotsParams,
  DeploymentSnapshotListResponse
> = ({ providerId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<DeploymentSnapshotListResponse> => {
    const { data } = await api.get<DeploymentSnapshotListResponse>(
      `${getURL("DEPLOYMENTS")}/snapshots`,
      { params: { provider_id: providerId, size: 50 } },
    );
    return data;
  };

  return query(
    ["useGetDeploymentSnapshots", { providerId }],
    fn,
    options,
  );
};
