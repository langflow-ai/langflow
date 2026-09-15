export interface ProviderScopeParams {
  flowId?: string;
  projectId?: string;
}

/**
 * How long a provider-policy snapshot (catalog, provider-variable mapping,
 * scoped credentials) is treated as current. Every provider-scoped query
 * shares this window so consumers can reason about a single freshness
 * boundary instead of a per-query one.
 */
export const PROVIDER_POLICY_STALE_TIME_MS = 30_000;

export const appendProviderScope = (
  queryParams: URLSearchParams,
  scope?: ProviderScopeParams,
): void => {
  if (scope?.flowId) {
    queryParams.append("flow_id", scope.flowId);
  }
  if (scope?.projectId) {
    queryParams.append("project_id", scope.projectId);
  }
};

export const providerScopeQueryKey = (scope?: ProviderScopeParams) =>
  [scope?.flowId, scope?.projectId] as const;

export const providerScopeStoreKey = (scope?: ProviderScopeParams): string => {
  if (scope?.flowId) return `flow:${scope.flowId}`;
  if (scope?.projectId) return `project:${scope.projectId}`;
  return "global";
};
