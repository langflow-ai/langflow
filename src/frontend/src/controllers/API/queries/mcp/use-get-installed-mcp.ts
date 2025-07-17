import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface IGetInstalledMCP {
  projectId: string;
}

type getInstalledMCPResponse = Array<string>;

export const useGetInstalledMCP: useQueryFunctionType<
  IGetInstalledMCP,
  getInstalledMCPResponse
> = (params, options) => {
  const { query } = UseRequestProcessor();

  const responseFn = async () => {
    try {
      const { data } = await api.get<getInstalledMCPResponse>(
        `${getURL("MCP")}/${params.projectId}/installed`,
      );
      return data;
    } catch (error) {
      console.error(error);
      return [];
    }
  };

  const queryResult = query(
    ["useGetInstalledMCP", params.projectId],
    responseFn,
    {
      ...options,
    },
  );

  return queryResult;
};
