import type { DeploymentFlowVersionItem } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import type {
  Deployment,
  DeploymentType,
} from "@/pages/MainPage/pages/deploymentsPage/types";
import { getDeploymentDisplayName } from "@/pages/MainPage/pages/deploymentsPage/types";

export interface FlowAttachment {
  deployment_id: string;
  deployment_name: string;
  deployment_type: DeploymentType;
  flow_version_id: string;
  provider_snapshot_id: string;
  current_version_tag: string;
  tool_name: string;
}

export function toReviewAttachments(
  deployment: Deployment,
  flowVersions: DeploymentFlowVersionItem[],
  fallbackToolName: string,
): FlowAttachment[] {
  return flowVersions
    .filter((item) => !!item.provider_snapshot_id)
    .map((item) => ({
      deployment_id: deployment.id,
      deployment_name: getDeploymentDisplayName(deployment),
      deployment_type: deployment.type,
      flow_version_id: item.id,
      provider_snapshot_id: item.provider_snapshot_id!,
      current_version_tag: `v${item.version_number}`,
      tool_name:
        item.provider_data?.tool_name?.trim() ||
        item.flow_name?.trim() ||
        fallbackToolName,
    }));
}
