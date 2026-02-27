import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionListResponse } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowHistoryParams {
  flowId: string;
  limit?: number;
  offset?: number;
}

export const useGetFlowHistory: useQueryFunctionType<
  FlowHistoryParams,
  FlowVersionListResponse
> = ({ flowId, limit = 50, offset = 0 }, options) => {
  const { query } = UseRequestProcessor();

  const getFlowHistoryFn = async (): Promise<FlowVersionListResponse> => {
    const response = await api.get<FlowVersionListResponse>(
      `${getURL("FLOWS")}/${flowId}/history/`,
      { params: { limit, offset } },
    );
    return response.data;
  };

  return query(
    ["useGetFlowHistory", { flowId, limit, offset }],
    getFlowHistoryFn,
    options,
  );
};
