import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AgentSpecItem, AgentMarketplaceResponse } from "./use-get-agent-marketplace";

interface AgentByFlowIdParams {
  flow_id: string;
}

export const useGetAgentByFlowId: useQueryFunctionType<
  AgentByFlowIdParams,
  AgentSpecItem | null
> = (params, options?) => {
  const { query } = UseRequestProcessor();

  const getAgentByFlowIdFn = async (): Promise<AgentSpecItem | null> => {
    // Fetch all marketplace agents
    const res = await api.get<AgentMarketplaceResponse>(
      `${getURL("AGENT_MARKETPLACE")}/`,
    );

    // Find the agent that matches the flow_id
    const agent = res.data.items.find(
      (item) => item.flow_id === params.flow_id
    );

    return agent || null;
  };

  const queryResult: UseQueryResult<AgentSpecItem | null, any> = query(
    ["useGetAgentByFlowId", params.flow_id],
    getAgentByFlowIdFn,
    {
      refetchOnWindowFocus: false,
      enabled: !!params.flow_id,
      ...options,
    },
  );

  return queryResult;
};
