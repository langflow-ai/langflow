import { useMutationFunctionType } from "@/types/api";
import { MCPServerType } from "@/types/mcp";
import { UseMutationResult } from "@tanstack/react-query";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface PatchMCPServerResponse {
  message: string;
}

export const usePatchMCPServer: useMutationFunctionType<
  undefined,
  MCPServerType,
  PatchMCPServerResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function patchMCPServer(
    body: MCPServerType,
  ): Promise<PatchMCPServerResponse> {
    try {
      let payload: Omit<MCPServerType, "name"> = {};

      if (body.url) {
        payload.url = body.url;
      }
      if (body.command) {
        payload.command = body.command;
      }
      if (body.args && body.args.length > 0) {
        payload.args = body.args;
      }
      if (body.env && Object.keys(body.env).length > 0) {
        payload.env = body.env;
      }

      const res = await api.patch(
        `${getURL("MCP_SERVERS", undefined, true)}/${body.name}`,
        payload,
      );

      return {
        message: res.data?.message || "MCP Server patched successfully",
      };
    } catch (error: any) {
      // Transform the error to include a message that can be handled by the UI
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "Failed to patch MCP Server";
      throw new Error(errorMessage);
    }
  }

  const mutation: UseMutationResult<
    PatchMCPServerResponse,
    any,
    MCPServerType
  > = mutate(["usePatchMCPServer"], patchMCPServer, {
    ...options,
    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetMCPServers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["useGetMCPServer", data.name],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
