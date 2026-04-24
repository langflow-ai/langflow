import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

/**
 * Attachment item from the /{deployment_id}/flows endpoint.
 *
 * Identity contract: Langflow tracks provider tools by their immutable
 * `provider_snapshot_id` (wxO tool_id), never by name.
 * - Tool renamed in provider → same snapshot ID, new `provider_data.tool_name`.
 * - Tool deleted in provider → missing from snapshot list, so
 *   `provider_data` is null for that attachment.
 * - Tool deleted + new tool created with same name → different ID, our
 *   attachment still points to the old (missing) ID. The new tool is
 *   invisible to Langflow until explicitly attached.
 *
 * When `provider_data` is non-null, `tool_name` is always present.
 * Fall back to `flow_name` when `provider_data` is null.
 * Use `provider_snapshot_id` for operations.
 */
export interface DeploymentFlowVersionItem {
  id: string;
  flow_id: string;
  flow_name: string | null;
  version_number: number;
  attached_at: string | null;
  provider_snapshot_id: string | null;
  provider_data: {
    app_ids?: string[];
    tool_name: string;
  } | null;
}

export interface DeploymentFlowVersionListResponse {
  flow_versions: DeploymentFlowVersionItem[];
  page: number;
  size: number;
  total: number;
}

interface GetDeploymentAttachmentsParams {
  deploymentId: string;
  flow_ids?: string[];
}

export const useGetDeploymentAttachments: useQueryFunctionType<
  GetDeploymentAttachmentsParams,
  DeploymentFlowVersionListResponse
> = ({ deploymentId, flow_ids }, options) => {
  const { query } = UseRequestProcessor();

  const fn = async (): Promise<DeploymentFlowVersionListResponse> => {
    const params = {
      size: 50,
      ...(flow_ids && flow_ids.length > 0 ? { flow_ids } : {}),
    };
    const { data } = await api.get<DeploymentFlowVersionListResponse>(
      `${getURL("DEPLOYMENTS")}/${deploymentId}/flows`,
      {
        params,
        paramsSerializer: { indexes: null },
      },
    );
    return data;
  };

  return query(
    ["useGetDeploymentAttachments", { deploymentId, flow_ids }],
    fn,
    options,
  );
};
