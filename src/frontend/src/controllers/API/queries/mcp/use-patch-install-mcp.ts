import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchInstallMCPParams {
  project_id: string;
}

interface PatchInstallMCPResponse {
  message: string;
}

export type MCPTransport = "sse" | "streamablehttp";

interface PatchInstallMCPBody {
  client: string;
  transport?: MCPTransport;
}

export const usePatchInstallMCP: useMutationFunctionType<
  PatchInstallMCPParams,
  PatchInstallMCPBody,
  PatchInstallMCPResponse
> = (params, options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchInstallMCP(
    body: PatchInstallMCPBody,
  ): Promise<PatchInstallMCPResponse> {
    try {
      const res = await api.post(
        `${getURL("MCP")}/${params.project_id}/install`,
        body,
      );

      return { message: res.data?.message || "MCP installed successfully" };
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to install MCP",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    PatchInstallMCPResponse,
    any,
    PatchInstallMCPBody
  > = mutate(["usePatchInstallMCP", params.project_id], patchInstallMCP, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetInstalledMCP", params.project_id],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
