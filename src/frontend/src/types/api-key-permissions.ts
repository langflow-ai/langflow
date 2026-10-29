export type ApiKeyScopeType = "global" | "workspace" | "project"; // pragma: allowlist secret

export interface ApiKeyPermissionScope {
  domain_type: ApiKeyScopeType;
  domain_id: string | null;
}

export interface ApiKeyRoleGrant extends ApiKeyPermissionScope {
  role_id: string;
}

export interface ApiKeyResourceRestriction extends ApiKeyPermissionScope {
  resource_type: string;
  actions: string[];
  resource_ids: string[] | null;
}

export interface ApiKeyPermissionPolicy {
  roles: ApiKeyRoleGrant[];
  restrictions: ApiKeyResourceRestriction[];
}

export interface ApiKeyPermissionOptions {
  supported: boolean;
  roles: Array<{
    id: string;
    name: string;
    description?: string | null;
    permissions: string[];
  }>;
  resource_actions: Record<string, string[]>;
  scope_types: Record<string, ApiKeyScopeType[]>;
}

export const emptyApiKeyPermissionPolicy = (): ApiKeyPermissionPolicy => ({
  roles: [],
  restrictions: [],
});

export function apiKeyPermissionPoliciesEqual(
  requested: ApiKeyPermissionPolicy | null,
  applied: ApiKeyPermissionPolicy | null | undefined,
): boolean {
  const canonical = (policy: ApiKeyPermissionPolicy | null | undefined) =>
    policy == null
      ? null
      : {
          roles: (policy.roles ?? []).map((role) => ({
            role_id: role.role_id.toLowerCase(),
            domain_type: role.domain_type ?? "global",
            domain_id: role.domain_id?.toLowerCase() ?? null,
          })),
          restrictions: (policy.restrictions ?? []).map((entry) => ({
            resource_type: entry.resource_type,
            actions: entry.actions,
            domain_type: entry.domain_type ?? "global",
            domain_id: entry.domain_id?.toLowerCase() ?? null,
            resource_ids: entry.resource_ids ?? null,
          })),
        };
  return (
    JSON.stringify(canonical(requested)) === JSON.stringify(canonical(applied))
  );
}
