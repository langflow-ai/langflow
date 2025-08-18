import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { AuthSettingsType, MCPSettingsType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchFlowMCPParams {
  project_id: string;
}

interface PatchFlowMCPRequest {
  settings: MCPSettingsType[];
  auth_settings?: AuthSettingsType;
}

interface PatchFlowMCPResponse {
  message: string;
}

export const usePatchFlowsMCP: useMutationFunctionType<
  PatchFlowMCPParams,
  PatchFlowMCPRequest,
  PatchFlowMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchFlowMCP(requestData: PatchFlowMCPRequest): Promise<any> {
    const res = await api.patch(
      `${getURL("MCP")}/${params.project_id}`,
      requestData,
    );
    return res.data.message;
  }

  const mutation: UseMutationResult<
    PatchFlowMCPResponse,
    any,
    PatchFlowMCPRequest
  > = mutate(["usePatchFlowsMCP"], patchFlowMCP, {
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFlowsMCP"] });
    },
    ...options,
  });

  return mutation;
};
