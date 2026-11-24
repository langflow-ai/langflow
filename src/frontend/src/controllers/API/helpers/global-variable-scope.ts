import {
  type ProviderScopeParams,
  providerScopeQueryKey,
} from "./provider-scope";

export const getGlobalVariablesQueryKey = (scope?: ProviderScopeParams) =>
  ["useGetGlobalVariables", ...providerScopeQueryKey(scope)] as const;
