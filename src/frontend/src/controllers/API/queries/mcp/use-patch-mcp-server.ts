import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { extractApiErrorMessage } from "../../helpers/extract-api-error-message";
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

      if (body.url !== undefined) {
        payload.url = body.url;
      }
      if (body.command !== undefined) {
        payload.command = body.command;
      }
      if (body.args !== undefined) {
        payload.args = body.args;
      }
      if (body.env !== undefined) {
        payload.env = body.env;
      }
      if (body.headers !== undefined) {
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
              ? { ...server, toolsCount: null, mode: null, error: undefined }
              : server;
          });
        },
      );

      return {
        message: res.data?.message || "MCP Server patched successfully",
      };
    } catch (error: unknown) {
      throw new Error(
        extractApiErrorMessage(
          error as Parameters<typeof extractApiErrorMessage>[0],
          "Failed to patch MCP Server",
        ),
      );
    }
  }

  const mutation: UseMutationResult<
    PatchMCPServerResponse,
    unknown,
    MCPServerType
  > = mutate(["usePatchMCPServer"], patchMCPServer, {
    ...options,
    retry: 0,

    onSuccess: (data, variables, context) => {
      queryClient.invalidateQueries({
        queryKey: ["useGetMCPServers"],
      });
      queryClient.invalidateQueries({
        queryKey: ["useGetMCPServer", variables.name],
      });
      options?.onSuccess?.(data, variables, context);
    },
  });

  return mutation;
};
