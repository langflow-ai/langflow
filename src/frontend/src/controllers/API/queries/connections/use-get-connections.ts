import type { useQueryFunctionType } from "@/types/api";
import { UseRequestProcessor } from "../../services/request-processor";
import { listConnections } from "./api";
import { connectionsKeys } from "./keys";
import type { ConnectionRead } from "./types";

export type { ConnectionRead } from "./types";

export interface GetConnectionsParams {
  /** Provider id from the component's `connection_ref` field, e.g. "google". */
  provider?: string;
  enabled?: boolean;
}

export const getConnectionsQueryKey = (provider?: string) =>
  connectionsKeys.list(provider);

export const useGetConnections: useQueryFunctionType<
  GetConnectionsParams | undefined,
  ConnectionRead[]
> = (params, options) => {
  const { query } = UseRequestProcessor();

  return query(
    connectionsKeys.list(params?.provider),
    () => listConnections(params?.provider),
    { refetchOnWindowFocus: true, ...options },
  );
};
