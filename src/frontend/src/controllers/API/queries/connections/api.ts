import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import type {
  ConnectionCreate,
  ConnectionRead,
  ConnectionRevokeRead,
  ConnectionUpdate,
  EffectiveIntegrationPolicyRead,
  IntegrationListRead,
  OAuthRegistrationListRead,
  OAuthRegistrationRead,
  OAuthStartResponse,
} from "./types";

const connections = () => getURL("CONNECTIONS");
const integrations = () => getURL("INTEGRATIONS");
const one = (id: string) => `${connections()}/${encodeURIComponent(id)}`;

/** The axios instance attaches auth and nothing else, so shapes are checked here. */
const asArray = <T>(value: unknown): T[] => (Array.isArray(value) ? value : []);

export async function listConnections(
  provider?: string,
): Promise<ConnectionRead[]> {
  const search = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  const { data } = await api.get<ConnectionRead[]>(`${connections()}${search}`);
  return asArray<ConnectionRead>(data);
}

/** There is no GET /connections/{id}; read the row out of the owner-scoped list. */
export async function getConnection(
  id: string,
): Promise<ConnectionRead | undefined> {
  const rows = await listConnections();
  return rows.find((row) => row.id === id);
}

export async function createConnection(
  payload: ConnectionCreate,
): Promise<ConnectionRead> {
  const { data } = await api.post<ConnectionRead>(connections(), payload);
  return data;
}

export async function updateConnection(
  id: string,
  patch: ConnectionUpdate,
): Promise<ConnectionRead> {
  const { data } = await api.patch<ConnectionRead>(one(id), patch);
  return data;
}

export async function testConnection(
  id: string,
  requiredScopes: string[] = [],
): Promise<ConnectionRead> {
  const { data } = await api.post<ConnectionRead>(`${one(id)}/test`, {
    required_scopes: requiredScopes,
  });
  return data;
}

export async function checkConnectionHealth(
  id: string,
): Promise<ConnectionRead> {
  const { data } = await api.post<ConnectionRead>(`${one(id)}/health`);
  return data;
}

export async function revokeConnection(
  id: string,
): Promise<ConnectionRevokeRead> {
  const { data } = await api.post<ConnectionRevokeRead>(`${one(id)}/revoke`);
  return data;
}

export async function deleteConnection(id: string): Promise<void> {
  await api.delete(one(id));
}

export async function startOAuth(
  id: string,
  registrationId: string,
  scopes: string[],
): Promise<OAuthStartResponse> {
  const { data } = await api.post<OAuthStartResponse>(
    `${one(id)}/oauth/start`,
    {
      registration_id: registrationId,
      scopes,
    },
  );
  return data;
}

/**
 * Registration configuration is operator-only, so the ids `oauth/start` accepts
 * come from here. Returns null when the backend predates the route, which lets a
 * caller fall back instead of reporting a failure nobody can act on.
 */
export async function listOAuthRegistrations(
  provider?: string,
): Promise<OAuthRegistrationRead[] | null> {
  const search = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  try {
    const { data } = await api.get<OAuthRegistrationListRead>(
      `${connections()}/oauth/registrations${search}`,
    );
    return asArray<OAuthRegistrationRead>(data?.registrations);
  } catch (error) {
    const status = (error as { response?: { status?: number } })?.response
      ?.status;
    if (status === 404) return null;
    throw error;
  }
}

export async function listIntegrations(options?: {
  provider?: string;
  includeBlocked?: boolean;
}): Promise<IntegrationListRead> {
  const query = new URLSearchParams();
  if (options?.provider) query.set("provider", options.provider);
  // include_blocked is superuser-only; the backend answers 403 for anyone else.
  if (options?.includeBlocked) query.set("include_blocked", "true");
  const suffix = query.toString();
  const { data } = await api.get<IntegrationListRead>(
    suffix ? `${integrations()}?${suffix}` : integrations(),
  );
  return {
    providers: asArray(data?.providers),
    deployment_context: data?.deployment_context,
  };
}

export async function getEffectiveIntegrationPolicy(): Promise<EffectiveIntegrationPolicyRead> {
  const { data } = await api.get<EffectiveIntegrationPolicyRead>(
    `${integrations()}/policy/effective`,
  );
  return data;
}
