import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  checkConnectionHealth,
  createConnection,
  deleteConnection,
  getConnection,
  getEffectiveIntegrationPolicy,
  listIntegrations,
  listOAuthRegistrations,
  revokeConnection,
  startOAuth,
  testConnection,
  updateConnection,
} from "./api";
import { connectionsKeys } from "./keys";
import type {
  ConnectionCreate,
  ConnectionRead,
  ConnectionRevokeRead,
  ConnectionUpdate,
  EffectiveIntegrationPolicyRead,
  IntegrationListRead,
  Iso8601,
  OAuthRegistrationRead,
  OAuthStartResponse,
} from "./types";

export const useInvalidateConnections = () => {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: connectionsKeys.all });
};

export const useIntegrationsQuery = (options?: {
  provider?: string;
  includeBlocked?: boolean;
  enabled?: boolean;
}) =>
  useQuery<IntegrationListRead>({
    queryKey: connectionsKeys.integrations(
      options?.provider,
      options?.includeBlocked,
    ),
    queryFn: () =>
      listIntegrations({
        provider: options?.provider,
        includeBlocked: options?.includeBlocked,
      }),
    enabled: options?.enabled ?? true,
    retry: 1,
  });

export const useEffectiveIntegrationPolicyQuery = (enabled = true) =>
  useQuery<EffectiveIntegrationPolicyRead>({
    queryKey: connectionsKeys.effectivePolicy(),
    queryFn: getEffectiveIntegrationPolicy,
    enabled,
    retry: 1,
  });

export const useOAuthRegistrationsQuery = (
  provider: string | undefined,
  enabled = true,
) =>
  useQuery<OAuthRegistrationRead[] | null>({
    queryKey: connectionsKeys.registrations(provider),
    queryFn: () => listOAuthRegistrations(provider),
    enabled,
    staleTime: 60_000,
    retry: 1,
  });

export const useCreateConnectionMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<ConnectionRead, unknown, ConnectionCreate>({
    mutationFn: createConnection,
    onSuccess: invalidate,
  });
};

export const useUpdateConnectionMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<
    ConnectionRead,
    unknown,
    { id: string; patch: ConnectionUpdate }
  >({
    mutationFn: ({ id, patch }) => updateConnection(id, patch),
    onSuccess: invalidate,
  });
};

export const useTestConnectionMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<
    ConnectionRead,
    unknown,
    { id: string; requiredScopes?: string[] }
  >({
    mutationFn: ({ id, requiredScopes }) => testConnection(id, requiredScopes),
    onSuccess: invalidate,
  });
};

export const useCheckConnectionHealthMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<ConnectionRead, unknown, string>({
    mutationFn: checkConnectionHealth,
    onSuccess: invalidate,
  });
};

export const useRevokeConnectionMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<ConnectionRevokeRead, unknown, string>({
    mutationFn: revokeConnection,
    onSuccess: invalidate,
  });
};

export const useDeleteConnectionMutation = () => {
  const invalidate = useInvalidateConnections();
  return useMutation<void, unknown, string>({
    mutationFn: deleteConnection,
    onSuccess: invalidate,
  });
};

export const useStartOAuthMutation = () =>
  useMutation<
    OAuthStartResponse,
    unknown,
    { id: string; registrationId: string; scopes: string[] }
  >({
    mutationFn: ({ id, registrationId, scopes }) =>
      startOAuth(id, registrationId, scopes),
  });

/**
 * The row as it stood when consent started. Consent completes on the server, in
 * another window, so a changed `updated_at` is the only honest signal that this
 * authorization landed: re-authorizing starts from `ready`, `expired` or
 * `revoked`, never `pending`.
 */
export interface ConnectionPollBaseline {
  id: string;
  updatedAt: Iso8601;
}

export const hasConsentLanded = (
  row: ConnectionRead | undefined,
  baseline: ConnectionPollBaseline | null,
): row is ConnectionRead =>
  !!row && !!baseline && row.updated_at !== baseline.updatedAt;

export const usePendingConnectionPoll = (
  baseline: ConnectionPollBaseline | null,
  options?: { intervalMs?: number },
) => {
  const interval = options?.intervalMs ?? 2000;
  return useQuery<ConnectionRead | undefined>({
    queryKey: connectionsKeys.one(baseline?.id ?? "none"),
    queryFn: () => getConnection(baseline?.id as string),
    enabled: baseline !== null,
    refetchInterval: (query) => {
      if (!baseline) return false;
      const row = query.state.data;
      return !row || row.updated_at === baseline.updatedAt ? interval : false;
    },
    refetchIntervalInBackground: true,
    retry: false,
  });
};
