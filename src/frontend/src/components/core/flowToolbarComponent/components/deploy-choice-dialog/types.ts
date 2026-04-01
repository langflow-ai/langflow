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

export function flattenToAttachments(
  deployments: Deployment[],
): FlowAttachment[] {
  const result: FlowAttachment[] = [];
  for (const dep of deployments) {
    if (!dep.matched_attachments) continue;
    for (const att of dep.matched_attachments) {
      if (!att.provider_snapshot_id) continue;
      result.push({
        deployment_id: dep.id,
        deployment_name: dep.name,
        deployment_type: dep.type,
        flow_version_id: att.flow_version_id,
        provider_snapshot_id: att.provider_snapshot_id,
      });
    }
  }
  return result;
}
