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
 * - Tool deleted in provider → snapshot ID unresolvable, `provider_data.tool_name` is null/missing.
 * - Tool deleted + new tool created with same name → different ID, our
 *   attachment still points to the old (missing) ID. The new tool is
 *   invisible to Langflow until explicitly attached.
 *
 * Use `provider_data.tool_name` for display, fall back to `flow_name` when null.
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
    /** Provider tool name — null/missing when the tool was deleted or provider is unreachable. */
    tool_name?: string | null;
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
