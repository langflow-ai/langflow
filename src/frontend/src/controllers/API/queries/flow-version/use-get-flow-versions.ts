import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionListResponse } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowVersionParams {
  flowId: string;
  limit?: number;
  offset?: number;
}

export const useGetFlowVersions: useQueryFunctionType<
  FlowVersionParams,
  FlowVersionListResponse
> = ({ flowId, limit = 50, offset = 0 }, options) => {
  const { query } = UseRequestProcessor();

  const getFlowVersionsFn = async (): Promise<FlowVersionListResponse> => {
    const response = await api.get<FlowVersionListResponse>(
      `${getURL("FLOWS")}/${flowId}/versions/`,
      { params: { limit, offset } },
    );
    return response.data;
  };

  return query(
    ["useGetFlowVersions", { flowId, limit, offset }],
    getFlowVersionsFn,
    options,
  );
};
