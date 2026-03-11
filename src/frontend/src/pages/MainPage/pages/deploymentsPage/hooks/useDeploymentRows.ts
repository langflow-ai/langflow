import type { DeploymentListItem } from "@/controllers/API/queries/deployments/use-deployments";
import { useMemo } from "react";
import type { DeploymentListRow } from "../components/DeploymentProvidersView";
import type { CreatedDeploymentUiMeta } from "../types";
import { formatDateLabel, mapProviderModeToLabel } from "../utils";

export type UseDeploymentRowsParams = {
  deployments: DeploymentListItem[];
  createdDeploymentItem: DeploymentListItem | null;
  createdDeploymentUiMeta: CreatedDeploymentUiMeta | null;
};

export const useDeploymentRows = ({
  deployments,
  createdDeploymentItem,
  createdDeploymentUiMeta,
}: UseDeploymentRowsParams) => {
  const liveDeployments = useMemo(() => {
    if (!createdDeploymentItem) {
      return deployments;
    }

    const deploymentsWithoutCreated = deployments.filter(
      (deployment) => deployment.id !== createdDeploymentItem.id,
    );
    return [createdDeploymentItem, ...deploymentsWithoutCreated];
  }, [deployments, createdDeploymentItem]);

  const deploymentRows = useMemo<DeploymentListRow[]>(() => {
    return liveDeployments.map((deployment) => {
      const providerDeploymentId =
        typeof deployment.resource_key === "string" &&
        deployment.resource_key.trim().length > 0
          ? deployment.resource_key
          : deployment.id;
      const deploymentRowId = deployment.id;
      const createdMeta =
        createdDeploymentUiMeta?.deploymentId === deploymentRowId
          ? createdDeploymentUiMeta
          : null;
      const snapshotIds =
        deployment.provider_data?.snapshot_ids &&
        Array.isArray(deployment.provider_data.snapshot_ids)
          ? deployment.provider_data.snapshot_ids
          : [];
      const mode =
        typeof deployment.provider_data?.mode === "string"
          ? deployment.provider_data.mode
          : undefined;

      return {
        id: deploymentRowId,
        name: deployment.name,
        url: `Deployment ID: ${providerDeploymentId}`,
        type: deployment.type.toUpperCase() === "MCP" ? "MCP" : "Agent",
        deploymentType:
          deployment.type.toUpperCase() === "MCP" ? "mcp" : "agent",
        mode: mapProviderModeToLabel(mode),
        status: mode === "live" ? ("Production" as const) : ("Draft" as const),
        health: "Healthy" as const,
        endpoint: providerDeploymentId,
        attached:
          deployment.attached_count ??
          createdMeta?.attachedCount ??
          snapshotIds.length ??
          0,
        modifiedDate: formatDateLabel(
          deployment.updated_at ??
            deployment.created_at ??
            createdMeta?.createdAt ??
            null,
        ),
        modifiedBy: "Unknown",
        createdDate: formatDateLabel(
          deployment.created_at ??
            deployment.updated_at ??
            createdMeta?.createdAt ??
            null,
        ),
      };
    });
  }, [createdDeploymentUiMeta, liveDeployments]);

  return { liveDeployments, deploymentRows };
};
