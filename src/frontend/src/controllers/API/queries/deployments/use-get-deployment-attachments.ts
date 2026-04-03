import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentFlowVersionItem {
  id: string;
  flow_id: string;
  flow_name: string | null;
  version_number: number;
  attached_at: string | null;
  provider_snapshot_id: string | null;
  provider_data: {
    app_ids?: string[];
  } | null;
  // TODO: Add tool_name field once the BE endpoint includes it.
  // The provider tool name (from the snapshot) is not yet surfaced
  // in the /flows response. For now, use flow_name as display fallback.
}

export interface DeploymentFlowVersionListResponse {
  flow_versions: DeploymentFlowVersionItem[];
  page: number;
  size: number;
  total: number;
}

interface GetDeploymentAttachmentsParams {
  deploymentId: string;
  flow_ids?: string;
}

export const useGetDeploymentAttachments: useQueryFunctionType<
  GetDeploymentAttachmentsParams,
  DeploymentFlowVersionListResponse
> = ({ deploymentId, flow_ids }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<DeploymentFlowVersionListResponse> => {
    const { data } = await api.get<DeploymentFlowVersionListResponse>(
      `${getURL("DEPLOYMENTS")}/${deploymentId}/flows`,
      { params: { size: 50, flow_ids } },
    );
    return data;
  };

  return query(
    ["useGetDeploymentAttachments", { deploymentId, flow_ids }],
    fn,
    options,
  );
};
