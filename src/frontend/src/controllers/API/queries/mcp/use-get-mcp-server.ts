import type { useMutationFunctionType } from "@/types/api";
import type { MCPServerType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type getMCPServerResponse = MCPServerType;

interface IGetMCPServer {
  name: string;
}

export const useGetMCPServer: useMutationFunctionType<
  undefined,
  IGetMCPServer,
  getMCPServerResponse
> = (options) => {
  const { mutate } = UseRequestProcessor();

  const responseFn = async (params: IGetMCPServer) => {
    const { data } = await api.get<Omit<getMCPServerResponse, "name">>(
      `${getURL("MCP_SERVERS", undefined, true)}/${params.name}`,
    );

    return { ...data, name: params.name };
  };

  const queryResult = mutate(["useGetMCPServer"], responseFn, {
    ...options,
  });

  return queryResult;
};
