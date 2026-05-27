export type DeploymentProviderType = "watsonx" | "kubernetes";

export const DEFAULT_FLOW_NAME = "Flow";
export const UNKNOWN_FLOW_NAME = "Unknown flow";
export const WXO_PROVIDER_KEY = "watsonx-orchestrate";

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

export function getDefaultDeploymentToolName(flowName: string) {
  const trimmedFlowName = flowName.trim() || DEFAULT_FLOW_NAME;
  return trimmedFlowName;
}

export interface Deployment {
  id: string;
  provider_id: string;
  description?: string | null;
  type: DeploymentType;
  created_at: string | null;
  updated_at: string | null;
  provider_data?: DeploymentProviderData | null;
  resource_key: string;
  attached_count: number;
  flow_version_ids?: string[];
}

export interface DeploymentProviderData extends Record<string, unknown> {
  display_name: string;
  name: string;
  environments?: string[];
  llm?: string | null;
}

export function getDeploymentDisplayName(deployment: Deployment | null) {
  if (!deployment) return "";
  return deployment.provider_data?.display_name ?? "";
}

export interface SnapshotUpdateResponse {
  flow_version_id: string;
  provider_snapshot_id: string;
}
