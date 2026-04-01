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
  provider_tenant_id: string | null;
  provider_key: string;
  provider_url: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ProviderCredentials {
  name: string;
  provider_key: string;
  provider_url: string;
  api_key: string;
}

export function toResourceNamePrefix(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export type DeploymentType = "agent" | "mcp";

export interface DeploymentMatchedAttachment {
  flow_version_id: string;
  provider_snapshot_id: string | null;
}

export interface Deployment {
  id: string;
  name: string;
  description: string | null;
  type: DeploymentType;
  created_at: string;
  updated_at: string;
  provider_data: Record<string, unknown> | null;
  resource_key: string;
  attached_count: number;
  matched_attachments: DeploymentMatchedAttachment[] | null;
  /** Populated client-side when merging deployments from multiple providers. */
  provider_account_id?: string;
}

export interface SnapshotUpdateResponse {
  flow_version_id: string;
  provider_snapshot_id: string;
}
