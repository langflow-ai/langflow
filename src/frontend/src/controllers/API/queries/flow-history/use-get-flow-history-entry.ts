import type { useQueryFunctionType } from "@/types/api";
import type { FlowHistoryEntryFull } from "@/types/flow/history";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowHistoryEntryParams {
  flowId: string;
  historyId: string;
}

export const useGetFlowHistoryEntry: useQueryFunctionType<
  FlowHistoryEntryParams,
  FlowHistoryEntryFull
> = ({ flowId, historyId }, options) => {
  const { query } = UseRequestProcessor();

  const getEntryFn = async (): Promise<FlowHistoryEntryFull> => {
    const response = await api.get<FlowHistoryEntryFull>(
      `${getURL("FLOWS")}/${flowId}/history/${historyId}`,
    );
    return response.data;
  };

  return query(["useGetFlowHistoryEntry", { flowId, historyId }], getEntryFn, {
    enabled: !!historyId,
    ...options,
  });
};
