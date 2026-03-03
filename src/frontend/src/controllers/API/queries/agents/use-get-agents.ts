import type { UseQueryResult } from "@tanstack/react-query";
import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AgentRead } from "./types";

export const useGetAgents: useQueryFunctionType<
  undefined,
  AgentRead[]
> = (options?) => {
  const { query } = UseRequestProcessor();

  const getAgentsFn = async (): Promise<AgentRead[]> => {
    const res = await api.get<AgentRead[]>(`${getURL("AGENTS")}/`);
    return res.data;
  };

  const queryResult: UseQueryResult<AgentRead[]> = query(
    ["useGetAgents"],
    getAgentsFn,
    {
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
