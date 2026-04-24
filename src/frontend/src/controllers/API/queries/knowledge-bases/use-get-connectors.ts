import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface ConnectorCatalogEntry {
  source_type: string;
  display_name: string;
  description: string;
  icon: string | null;
  requires_credentials: boolean;
}

export const useGetConnectors: useQueryFunctionType<
  undefined,
  ConnectorCatalogEntry[]
> = (_params, options?) => {
  const { query } = UseRequestProcessor();

  const getConnectorsFn = async (): Promise<ConnectorCatalogEntry[]> => {
    const url = `${getURL("KNOWLEDGE_BASES")}/connectors`;
    const res = await api.get<ConnectorCatalogEntry[]>(url);
    return res.data;
  };

  const queryResult: UseQueryResult<ConnectorCatalogEntry[], Error> = query(
    ["useGetConnectors"],
    getConnectorsFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
      ...options,
    },
  );

  return queryResult;
};
