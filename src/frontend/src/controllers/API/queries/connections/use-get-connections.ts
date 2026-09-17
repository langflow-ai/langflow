import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

/** Credential-free connection metadata, mirroring `ConnectionRead`. */
export interface ConnectionRead {
  id: string;
  owner_id: string | null;
  ownership_mode: "user" | "instance";
  provider_key: string;
  name: string;
  display_name: string;
  status: "pending" | "ready" | "expired" | "revoked" | "error";
  status_reason?: "credential-missing" | "credential-undecryptable" | null;
  health: "unknown" | "healthy" | "unhealthy";
  granted_scopes: string[];
  executing_identity: {
    identity: string;
    account?: {
      id: string;
      display?: string | null;
      tenant_id?: string | null;
    } | null;
  };
  allow_non_interactive: boolean;
  has_credentials: boolean;
  health_checked_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface GetConnectionsParams {
  /** Provider id from the component's `connection_ref` field, e.g. "google". */
  provider?: string;
  enabled?: boolean;
}

export const getConnectionsQueryKey = (provider?: string) =>
  ["useGetConnections", provider ?? "all"] as const;

export const useGetConnections: useQueryFunctionType<
  GetConnectionsParams | undefined,
  ConnectionRead[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const getConnectionsFn = async (): Promise<ConnectionRead[]> => {
    const search = params?.provider
      ? `?provider=${encodeURIComponent(params.provider)}`
      : "";
    const response = await api.get<ConnectionRead[]>(
      `${getURL("CONNECTIONS")}${search}`,
    );
    return response.data;
  };

  return query(getConnectionsQueryKey(params?.provider), getConnectionsFn, {
    refetchOnWindowFocus: true,
    ...options,
  });
};
