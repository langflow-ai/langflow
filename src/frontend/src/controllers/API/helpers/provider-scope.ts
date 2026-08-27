export interface ProviderScopeParams {
  flowId?: string;
  projectId?: string;
}

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
