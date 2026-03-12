import type { useQueryFunctionType } from "@/types/api";
import type { FlowHistoryListResponse } from "@/types/flow/history";
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
  FlowHistoryListResponse
> = ({ flowId, limit = 50, offset = 0 }, options) => {
  const { query } = UseRequestProcessor();

  const getFlowHistoryFn = async (): Promise<FlowHistoryListResponse> => {
    try {
      const response = await api.get<FlowHistoryListResponse>(
        `${getURL("FLOWS")}/${flowId}/history/`,
        { params: { limit, offset } },
      );
      return response.data;
    } catch {
      const response = await api.get<FlowHistoryListResponse>(
        `${getURL("FLOWS")}/${flowId}/versions/`,
        { params: { limit, offset } },
      );
      return response.data;
    }
  };

  return query(
    ["useGetFlowHistory", { flowId, limit, offset }],
    getFlowHistoryFn,
    options,
  );
};
