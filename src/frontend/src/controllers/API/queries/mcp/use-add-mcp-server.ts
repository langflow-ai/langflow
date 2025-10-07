import type { UseMutationResult } from "@tanstack/react-query";
import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface AddMCPServerResponse {
  message: string;
}

export const useAddMCPServer: useMutationFunctionType<
  undefined,
  MCPServerType,
  AddMCPServerResponse
> = (options?) => {
  const { mutate, queryClient } = UseRequestProcessor();

  async function addMCPServer(
    body: MCPServerType,
  ): Promise<AddMCPServerResponse> {
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

      const res = await api.post(
        `${getURL("MCP_SERVERS", undefined, true)}/${body.name}`,
        payload,
      );

      return { message: res.data?.message || "MCP Server added successfully" };
    } catch (error: any) {
      // Transform the error to include a message that can be handled by the UI
      const errorMessage =
        error.response?.data?.detail ||
        error.message ||
        "Failed to install MCP";
      throw new Error(errorMessage);
    }
  }

  const mutation: UseMutationResult<AddMCPServerResponse, any, MCPServerType> =
    mutate(["useAddMCPServer"], addMCPServer, {
      ...options,
      retry: 0,
      onSuccess: (data, variables, context) => {
        queryClient.invalidateQueries({
          queryKey: ["useGetMCPServers"],
        });
        options?.onSuccess?.(data, variables, context);
      },
    });

  return mutation;
};
