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

function getShortIdentifier(value: string) {
  const normalizedValue = value.trim();
  const compactValue = normalizedValue.includes("-")
    ? normalizedValue.split("-").at(-1) || normalizedValue
    : normalizedValue;
  return compactValue.slice(0, 8) || "tool";
}

export function createDeploymentToolNameScopeId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

export function getDefaultDeploymentToolName(
  flowName: string,
  uniqueId: string,
  scopeId?: string | null,
) {
  const trimmedFlowName = flowName.trim() || DEFAULT_FLOW_NAME;
  const shortId = getShortIdentifier(uniqueId);
  const shortScopeId = scopeId ? getShortIdentifier(scopeId).slice(0, 6) : "";
  return shortScopeId
    ? `${trimmedFlowName} ${shortScopeId}-${shortId}`
    : `${trimmedFlowName} ${shortId}`;
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
