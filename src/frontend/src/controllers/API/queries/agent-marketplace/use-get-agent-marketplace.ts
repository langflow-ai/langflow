import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export interface AgentSpecError {
  folder_name: string;
  file_name: string;
  message: string;
}

export interface AgentSpecItem {
  folder_name: string;
  file_name: string;
  flow_id?: string | null;
  flow_icon?: string | null;
  status?: string;
  // Spec schema is flexible; we surface name/description/tags when present
  spec: {
    name?: string;
    description?: string;
    tags?: string[];
    [key: string]: any;
  };
}

export interface AgentMarketplaceResponse {
  items: AgentSpecItem[];
  total: number;
  requested_folder?: string | null;
  errors?: AgentSpecError[];
}

interface AgentMarketplaceParams {
  folder_name?: string;
}

export const useGetAgentMarketplaceQuery: useQueryFunctionType<
  AgentMarketplaceParams | undefined,
  AgentMarketplaceResponse
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getAgentMarketplaceFn = async (): Promise<AgentMarketplaceResponse> => {
    const config: any = {};
    if (params?.folder_name) {
      config.params = { folder_name: params.folder_name };
    }
    const res = await api.get<AgentMarketplaceResponse>(
      `${getURL("AGENT_MARKETPLACE")}/`,
      config,
    );
    return res.data;
  };

  const queryResult: UseQueryResult<AgentMarketplaceResponse, any> = query(
    ["useGetAgentMarketplaceQuery", { key: params?.folder_name }],
    getAgentMarketplaceFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};