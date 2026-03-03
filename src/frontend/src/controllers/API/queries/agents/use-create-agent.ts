import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AgentCreate, AgentRead } from "./types";

export const useCreateAgent: useMutationFunctionType<
  undefined,
  AgentCreate,
  AgentRead
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const createAgentFn = async (payload: AgentCreate): Promise<AgentRead> => {
    const res = await api.post<AgentRead>(`${getURL("AGENTS")}/`, payload);
    return res.data;
  };

  const mutation: UseMutationResult<AgentRead, unknown, AgentCreate> = mutate(
    ["useCreateAgent"],
    createAgentFn,
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["useGetAgents"] });
      },
      ...options,
    },
  );

  return mutation;
};
