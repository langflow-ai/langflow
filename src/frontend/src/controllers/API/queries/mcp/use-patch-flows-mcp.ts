import type { useMutationFunctionType } from "@/types/api";
import type { MCPSettingsType } from "@/types/mcp";
import type { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchFlowMCPParams {
  project_id: string;
}

interface PatchFlowMCPResponse {
  message: string;
}

export const usePatchFlowsMCP: useMutationFunctionType<
  PatchFlowMCPParams,
  MCPSettingsType[],
  PatchFlowMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchFlowMCP(flowMCP: MCPSettingsType[]): Promise<any> {
    const res = await api.patch(
      `${getURL("MCP")}/${params.project_id}`,
      flowMCP,
    );
    return res.data.message;
  }

  const mutation: UseMutationResult<
    PatchFlowMCPResponse,
    any,
    MCPSettingsType[]
  > = mutate(["usePatchFlowsMCP"], patchFlowMCP, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFlowsMCP"] });
    },
    ...options,
  });

  return mutation;
};
