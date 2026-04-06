export type DeploymentProviderType = "watsonx" | "kubernetes";

export interface EnvVarEntry {
  id: string;
  key: string;
  value: string;
  globalVar?: boolean;
}

export interface ConnectionItem {
  id: string;
  name: string;
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
  url: string;
  provider_data?: Record<string, unknown>;
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

export interface Deployment {
  id: string;
  name: string;
  description?: string;
  type: DeploymentType;
  created_at: string;
  updated_at: string;
  provider_data?: Record<string, unknown>;
  resource_key: string;
  attached_count: number;
  flow_version_ids?: string[];
  /** Populated client-side when merging deployments from multiple providers. */
  provider_account_id?: string;
}

export interface SnapshotUpdateResponse {
  flow_version_id: string;
  provider_snapshot_id: string;
}
