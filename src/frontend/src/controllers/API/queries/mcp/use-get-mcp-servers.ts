import { useQueryFunctionType } from "@/types/api";
import { MCPServerInfoType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

type getMCPServersResponse = Array<MCPServerInfoType>;

export const useGetMCPServers: useQueryFunctionType<
  undefined,
  getMCPServersResponse
> = (options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    try {
      const { data } = await api.get<getMCPServersResponse>(
        `${getURL("MCP_SERVERS", undefined, true)}`,
      );
      return data;
    } catch (error) {
      console.error(error);
      return [];
    }
  };

  const queryResult = query(["useGetMCPServers"], responseFn, {
    ...options,
  });

  return queryResult;
};
