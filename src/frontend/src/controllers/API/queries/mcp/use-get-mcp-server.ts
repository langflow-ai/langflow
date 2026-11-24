import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";
import {
  isNotFoundResponse,
  McpServerNotFoundError,
  refreshMcpServerList,
} from "./mcp-server-not-found-error";

type getMCPServerResponse = MCPServerType;

interface IGetMCPServer {
  name: string;
}

export const useGetMCPServer: useMutationFunctionType<
  undefined,
  IGetMCPServer,
  getMCPServerResponse
> = (options) => {
  const { mutate, queryClient } = UseRequestProcessor();

  const responseFn = async (params: IGetMCPServer) => {
    try {
      const { data } = await api.get<Omit<getMCPServerResponse, "name">>(
        `${getURL("MCP_SERVERS", undefined, true)}/${params.name}`,
      );

      return { ...data, name: params.name };
    } catch (error: unknown) {
      if (isNotFoundResponse(error)) {
        refreshMcpServerList(queryClient);
        throw new McpServerNotFoundError(params.name);
      }
      throw error;
    }
  };

  const queryResult = mutate(["useGetMCPServer"], responseFn, {
    ...options,
  });

  return queryResult;
};
