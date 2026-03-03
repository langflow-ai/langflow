import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

export const useDeleteAgent: useMutationFunctionType<
  undefined,
  string,
  void
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const deleteAgentFn = async (agentId: string): Promise<void> => {
    await api.delete(`${getURL("AGENTS")}/${agentId}`);
  };

  const mutation: UseMutationResult<void, unknown, string> = mutate(
    ["useDeleteAgent"],
    deleteAgentFn,
    {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["useGetAgents"] });
      },
      ...options,
    },
  );

  return mutation;
};
