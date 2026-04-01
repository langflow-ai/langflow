import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface DeploymentAttachmentItem {
  flow_version_id: string;
  flow_id: string;
  flow_name: string;
  version_tag: string;
  provider_snapshot_id: string | null;
  connection_ids: string[];
  created_at: string | null;
}

export interface DeploymentAttachmentListResponse {
  attachments: DeploymentAttachmentItem[];
  llm: string | null;
}

interface GetDeploymentAttachmentsParams {
  deploymentId: string;
}

export const useGetDeploymentAttachments: useQueryFunctionType<
  GetDeploymentAttachmentsParams,
  DeploymentAttachmentListResponse
> = ({ deploymentId }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<DeploymentAttachmentListResponse> => {
    const { data } = await api.get<DeploymentAttachmentListResponse>(
      `${getURL("DEPLOYMENTS")}/${deploymentId}/attachments`,
    );
    return data;
  };

  return query(
    ["useGetDeploymentAttachments", { deploymentId }],
    fn,
    options,
  );
};
