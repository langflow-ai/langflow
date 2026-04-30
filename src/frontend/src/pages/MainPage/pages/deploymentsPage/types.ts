export type DeploymentProviderType = "watsonx" | "kubernetes";

export interface EnvVarEntry {
  id: string;
  key: string;
  value: string;
  globalVar?: boolean;
}

export interface ConnectionItem {
  id: string;
  connectionId: string;
  name: string;
  environment?: string;
  variableCount: number;
  isNew: boolean;
  environmentVariables: Record<string, string>;
  globalVarKeys?: Set<string>;
}

export interface DeploymentProvider {
  id: string;
  type: DeploymentProviderType;
  name: string;
  icon: string;
}

export interface ProviderAccount {
  id: string;
  name: string;
  provider_key: string;
  provider_data?: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProviderCredentials {
  name: string;
  provider_key: string;
  url: string;
  api_key: string;
}

export type DeploymentType = "agent" | "mcp";

export interface SelectedFlowVersion {
  key: string;
  flowId: string;
  flowName?: string;
  versionId: string;
  versionTag: string;
}

export function getSelectedFlowVersionKey(flowId: string, versionId: string) {
  return `${flowId}:${versionId}`;
}

export function getDefaultDeploymentToolName(
  flowName: string,
  uniqueId: string,
) {
  const trimmedFlowName = flowName.trim() || "Flow";
  const normalizedId = uniqueId.trim();
  const compactId = normalizedId.includes("-")
    ? normalizedId.split("-").at(-1) || normalizedId
    : normalizedId;
  const shortId = compactId.slice(0, 8) || "tool";
  return `${trimmedFlowName} ${shortId}`;
}

export interface Deployment {
  id: string;
  provider_id?: string;
  name: string;
  description?: string;
  type: DeploymentType;
  created_at: string;
  updated_at: string;
  provider_data?: Record<string, unknown>;
  resource_key: string;
  attached_count: number;
  flow_version_ids?: string[];
}

export interface SnapshotUpdateResponse {
  flow_version_id: string;
  provider_snapshot_id: string;
}
