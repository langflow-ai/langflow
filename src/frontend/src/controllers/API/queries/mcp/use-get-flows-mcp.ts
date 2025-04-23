import { useQueryFunctionType } from "@/types/api";
import { MCPSettingsType } from "@/types/mcp";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetFlowsMCP {
  projectId: string;
}

type getFlowsMCPResponse = Array<MCPSettingsType>;

export const useGetFlowsMCP: useQueryFunctionType<
  IGetFlowsMCP,
  getFlowsMCPResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    const { data } = await api.get<getFlowsMCPResponse>(
      `${getURL("MCP")}/${params.projectId}/?mcp_enabled_only=false`,
    );
    return data;
  };

  const queryResult = query(["useGetFlowsMCP"], responseFn, {
    ...options,
  });

  return queryResult;
};
