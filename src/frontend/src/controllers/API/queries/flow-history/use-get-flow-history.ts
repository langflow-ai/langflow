import type { useQueryFunctionType } from "@/types/api";
import type { FlowHistoryEntry } from "@/types/flow/history";
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
  FlowHistoryEntry[]
> = ({ flowId, limit = 50, offset = 0 }, options) => {
  const { query } = UseRequestProcessor();

  const getFlowHistoryFn = async (): Promise<FlowHistoryEntry[]> => {
    const response = await api.get<FlowHistoryEntry[]>(
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
