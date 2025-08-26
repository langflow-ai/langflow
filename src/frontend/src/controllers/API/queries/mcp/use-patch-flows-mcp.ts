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
  composer_url?: {
    project_id: string;
    composer_port: number;
    composer_host: string;
    composer_sse_url: string;
  };
}

export const usePatchFlowsMCP: useMutationFunctionType<
  PatchFlowMCPParams,
  PatchFlowMCPRequest,
  PatchFlowMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchFlowMCP(requestData: PatchFlowMCPRequest): Promise<PatchFlowMCPResponse> {
    const res = await api.patch(
      `${getURL("MCP")}/${params.project_id}`,
      requestData,
    );
    return res.data;
  }

  const mutation: UseMutationResult<
    PatchFlowMCPResponse,
    any,
    PatchFlowMCPRequest
  > = mutate(["usePatchFlowsMCP"], patchFlowMCP, {
    onSuccess: (data, variables, context) => {
      // If composer URL is included in response, update the query cache directly
      if (data.composer_url) {
        queryClient.setQueryData(
          ["project-composer-url", params.project_id],
          data.composer_url
        );
      }
      
      // Call the original onSuccess if provided
      if (options?.onSuccess) {
        options.onSuccess(data, variables, context);
      }
    },
    onSettled: () => {
      queryClient.refetchQueries({ queryKey: ["useGetFlowsMCP"] });
      // Only invalidate composer URL query if no composer_url in response
      // (fallback for non-OAuth projects)
      queryClient.invalidateQueries({ queryKey: ["project-composer-url", params.project_id] });
    },
    ...options,
  });

  return mutation;
};
