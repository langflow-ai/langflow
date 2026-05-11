import type { DeploymentFlowVersionItem } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";
import type {
  Deployment,
  DeploymentType,
} from "@/pages/MainPage/pages/deploymentsPage/types";

export interface FlowAttachment {
  deployment_id: string;
  deployment_name: string;
  deployment_type: DeploymentType;
  flow_version_id: string;
  provider_snapshot_id: string;
}

export function toReviewAttachment(
  deployment: Deployment,
  flowVersions: DeploymentFlowVersionItem[],
): FlowAttachment | null {
  const selectedFlowVersion = flowVersions.find(
    (item) => !!item.provider_snapshot_id,
  );
  if (!selectedFlowVersion?.provider_snapshot_id) {
    return null;
  }

  return {
    deployment_id: deployment.id,
    deployment_name: deployment.name,
    deployment_type: deployment.type,
    flow_version_id: selectedFlowVersion.id,
    provider_snapshot_id: selectedFlowVersion.provider_snapshot_id,
  };
}
