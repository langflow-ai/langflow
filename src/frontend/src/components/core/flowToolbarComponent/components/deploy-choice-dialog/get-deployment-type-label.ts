import type { DeploymentType } from "@/pages/MainPage/pages/deploymentsPage/types";

/**
 * Maps a deployment type to its localized label. Falls back to the raw
 * type value for types without a translated key (e.g. future types added
 * server-side before the locale catalog catches up).
 */
export function getDeploymentTypeLabel(
  deploymentType: DeploymentType,
  t: (key: string) => string,
): string {
  if (deploymentType === "agent") {
    return t("deployments.agentTypeLabel");
  }

  if (deploymentType === "mcp") {
    return t("deployments.mcpTypeLabel");
  }

  return deploymentType;
}
