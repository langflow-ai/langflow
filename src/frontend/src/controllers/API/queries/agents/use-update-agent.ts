import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { AgentRead, AgentUpdate } from "./types";

interface UpdateAgentPayload {
  agentId: string;
  data: AgentUpdate;
}

export const useUpdateAgent: useMutationFunctionType<
  undefined,
  UpdateAgentPayload,
  AgentRead
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const updateAgentFn = async (
    payload: UpdateAgentPayload,
  ): Promise<AgentRead> => {
    const res = await api.patch<AgentRead>(
      `${getURL("AGENTS")}/${payload.agentId}`,
      payload.data,
    );
    return res.data;
  };

  const mutation: UseMutationResult<AgentRead, unknown, UpdateAgentPayload> =
    mutate(["useUpdateAgent"], updateAgentFn, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["useGetAgents"] });
      },
      ...options,
    });

  return mutation;
};
