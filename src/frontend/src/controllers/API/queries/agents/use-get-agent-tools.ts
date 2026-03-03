import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AgentToolInfo } from "./types";

export const useGetAgentTools: useQueryFunctionType<
  undefined,
  AgentToolInfo[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getToolsFn = async (): Promise<AgentToolInfo[]> => {
    const res = await api.get<AgentToolInfo[]>(`${getURL("AGENT_TOOLS")}`);
    return res.data;
  };

  const queryResult: UseQueryResult<AgentToolInfo[]> = query(
    ["useGetAgentTools"],
    getToolsFn,
    {
      refetchOnWindowFocus: false,
      staleTime: 5 * 60 * 1000,
      ...options,
    },
  );

  return queryResult;
};
