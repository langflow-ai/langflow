/**
 * Wire types for managed connections and the integration catalog.
 *
 * These mirror the backend schemas (`connection/schemas.py`,
 * `api/v1/integrations.py`), so field names stay snake_case. A distribution that
 * builds its own connections UI imports them from here rather than redeclaring
 * them and drifting.
 */

export type Iso8601 = string;

export type ConnectionOwnershipMode = "user" | "instance";

export type ConnectionStatus =
  | "pending"
  | "ready"
  | "expired"
  | "revoked"
  | "error";

export type ConnectionStatusReason =
  | "credential-missing"
  | "credential-undecryptable";

export type ConnectionHealth = "unknown" | "healthy" | "unhealthy";

export type IntegrationIdentity = "user_delegated" | "bot" | "service";

export type ProviderRevocation =
  | "revoked"
  | "unsupported"
  | "failed"
  | "not_applicable";

/**
 * Keep in sync with CONNECTION_NAME_PATTERN and ConnectionRef.name in
 * src/lfx/src/lfx/integrations/models.py (enforced by types.test.ts).
 */
export const CONNECTION_NAME_PATTERN = /^[a-z0-9]+(?:_[a-z0-9]+)*$/;
export const CONNECTION_NAME_MAX_LENGTH = 64;

export interface ConnectionAccount {
  id: string;
  display?: string | null;
  tenant_id?: string | null;
}

export interface ExecutingIdentityDescriptor {
  identity: IntegrationIdentity;
  account?: ConnectionAccount | null;
}

/** Credential-free connection metadata; no route ever returns token material. */
export interface ConnectionRead {
  id: string;
  owner_id: string | null;
  ownership_mode: ConnectionOwnershipMode;
  provider_key: string;
  name: string;
  display_name: string;
  status: ConnectionStatus;
  status_reason?: ConnectionStatusReason | null;
  health: ConnectionHealth;
  granted_scopes: string[];
  executing_identity: ExecutingIdentityDescriptor;
  allow_non_interactive: boolean;
  has_credentials: boolean;
  health_checked_at: string | null;
  created_at: Iso8601;
  updated_at: Iso8601;
}

export interface ConnectionRevokeRead extends ConnectionRead {
  provider_revocation: ProviderRevocation;
}

export interface ConnectionCredentialWrite {
  access_token: string;
  refresh_token?: string | null;
  token_type?: string;
  expires_at?: Iso8601 | null;
}

export interface ConnectionCreate {
  provider_key: string;
  name: string;
  display_name: string;
  ownership_mode?: ConnectionOwnershipMode;
  granted_scopes?: string[];
  executing_identity: ExecutingIdentityDescriptor;
  allow_non_interactive?: boolean;
  credentials?: ConnectionCredentialWrite | null;
}

/** Only these two change without re-authorizing the provider. */
export interface ConnectionUpdate {
  display_name?: string;
  allow_non_interactive?: boolean;
}

export interface OAuthStartResponse {
  authorization_url: string;
}

/** One operator-configured registration, as the listing route returns it. */
export interface OAuthRegistrationRead {
  id: string;
  provider: string;
  profile: "user" | "bot";
  context: "self_managed" | "hosted" | "desktop";
  client_type: "confidential" | "public";
  scopes: string[];
  allowed_tenants: string[];
}

export interface OAuthRegistrationListRead {
  registrations: OAuthRegistrationRead[];
}

export interface IntegrationCapabilityRead {
  id: string;
  display_name: string;
  policy_keys: string[];
  risk: string;
  maturity: string;
  substrate: string;
  identity: IntegrationIdentity;
  auth_profile_id: string;
  deployment_contexts: string[];
  component_ref?: string | null;
  mcp_tool?: string | null;
  allowed: boolean;
  blocked_policy_key?: string | null;
}

export interface IntegrationProviderRead {
  provider_id: string;
  display_name: string;
  icon?: string | null;
  docs_url?: string | null;
  approved: boolean;
  enabled: boolean;
  connection_count: number;
  capabilities: IntegrationCapabilityRead[];
}

export interface IntegrationListRead {
  providers: IntegrationProviderRead[];
}

/** What the caller may use, and whether a plugin owns the decision. */
export interface EffectiveIntegrationPolicyRead {
  approved_provider_ids: string[];
  blocked_action_keys: string[];
  loaded_provider_ids: string[];
  unrestricted: boolean;
  managed_externally: boolean;
  policy_revision: number | null;
}

export const connectionHandle = (
  connection: Pick<ConnectionRead, "provider_key" | "name">,
): string => `${connection.provider_key}/${connection.name}`;
