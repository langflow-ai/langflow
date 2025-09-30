import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import type { getMCPServersResponse } from "./use-get-mcp-servers";

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
      const payload: Omit<MCPServerType, "name"> = {};

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
      if (body.headers && Object.keys(body.headers).length > 0) {
        payload.headers = body.headers;
      }

      const res = await api.patch(
        `${getURL("MCP_SERVERS", undefined, true)}/${body.name}`,
        payload,
      );

      queryClient.setQueryData(
        ["useGetMCPServers"],
        (oldData: getMCPServersResponse = []) => {
          return oldData.map((server) => {
            return server.name === body.name
              ? { ...server, toolsCount: null }
              : server;
          });
        },
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
