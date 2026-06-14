import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
import { UseRequestProcessor } from "../../services/request-processor";

interface DeleteMCPServerResponse {
  message: string;
}

interface DeleteMCPServerType {
  name: string;
}

export const useDeleteMCPServer: useMutationFunctionType<
  undefined,
  DeleteMCPServerType,
  DeleteMCPServerResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function deleteMCPServer(
    payload: MCPServerType,
  ): Promise<DeleteMCPServerResponse> {
    try {
      const res = await api.delete(
        `${getURL("MCP_SERVERS", undefined, true)}/${payload.name}`,
      );

      return {
        message: res.data?.message || "MCP Server deleted successfully",
      };
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to delete MCP Server",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    DeleteMCPServerResponse,
    any,
    MCPServerType
  > = mutate(["useDeleteMCPServer"], deleteMCPServer, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.refetchQueries({
        queryKey: ["useGetMCPServers"],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
