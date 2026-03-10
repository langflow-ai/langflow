import type { useQueryFunctionType } from "@/types/api";
import type { FlowHistoryEntryWithData } from "@/types/flow/history";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowHistoryEntryParams {
  flowId: string;
  historyId: string;
}

export const useGetFlowHistoryEntry: useQueryFunctionType<
  FlowHistoryEntryParams,
  FlowHistoryEntryWithData
> = ({ flowId, historyId }, options) => {
  const { query } = UseRequestProcessor();

  const getEntryFn = async (): Promise<FlowHistoryEntryWithData> => {
    const response = await api.get<FlowHistoryEntryWithData>(
      `${getURL("FLOWS")}/${flowId}/history/${historyId}`,
    );
    return response.data;
  };

  return query(["useGetFlowHistoryEntry", { flowId, historyId }], getEntryFn, {
    ...options,
    enabled: !!historyId && (options?.enabled ?? true),
  });
};
