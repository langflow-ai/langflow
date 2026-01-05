import type { useQueryFunctionType } from "@/types/api";
import type { MCPProjectResponseType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFlowsMCP {
  projectId: string;
}

type getFlowsMCPResponse = MCPProjectResponseType;

export const useGetFlowsMCP: useQueryFunctionType<
  IGetFlowsMCP,
  getFlowsMCPResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    try {
      const { data } = await api.get<getFlowsMCPResponse>(
        `${getURL("MCP")}/${params.projectId}?mcp_enabled=false`,
      );
      return data;
    } catch (error) {
      console.error(error);
      return { tools: [], auth_settings: undefined };
    }
  };

  const queryResult = query(["useGetFlowsMCP", params.projectId], responseFn, {
    ...options,
  });

  return queryResult;
};
