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
  result?: {
    project_id: string;
    sse_url: string;
    uses_composer: boolean;
  };
}

export const usePatchFlowsMCP: useMutationFunctionType<
  PatchFlowMCPParams,
  PatchFlowMCPRequest,
  PatchFlowMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchFlowMCP(
    requestData: PatchFlowMCPRequest,
  ): Promise<PatchFlowMCPResponse> {
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
      // Update the auth settings cache immediately to prevent race conditions
      const currentMCPData = queryClient.getQueryData(["useGetFlowsMCP", params.project_id]);
      if (currentMCPData && variables.auth_settings) {
        queryClient.setQueryData(["useGetFlowsMCP", params.project_id], {
          ...currentMCPData,
          auth_settings: variables.auth_settings,
        });
      }

      // Update the cache with the exact SSE URL from the backend
      if (data.result?.sse_url) {
        if (data.result.uses_composer) {
          const composerUrlData = {
            project_id: data.result.project_id,
            sse_url: data.result.sse_url,
          };
          queryClient.setQueryData(
            ["project-composer-url", params.project_id],
            composerUrlData,
          );
        } else {
          // OAuth disabled - remove composer cache and let UI fall back to direct SSE
          // The direct SSE URL logic is already in customGetMCPUrl, so we just clear the composer cache
          queryClient.removeQueries({
            queryKey: ["project-composer-url", params.project_id],
          });
        }
      }

      // Call the original onSuccess if provided
      if (options?.onSuccess) {
        options.onSuccess(data, variables, context);
      }
    },
    onSettled: () => {
      // Use invalidateQueries instead of refetchQueries to avoid race conditions
      // This marks the queries as stale but doesn't immediately refetch them
      queryClient.invalidateQueries({ queryKey: ["useGetFlowsMCP"] });
    },
    ...options,
  });

  return mutation;
};
