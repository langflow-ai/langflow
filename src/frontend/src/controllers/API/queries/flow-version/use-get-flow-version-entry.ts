import type { useQueryFunctionType } from "@/types/api";
import type { FlowVersionEntryWithData } from "@/types/flow/version";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowHistoryEntryParams {
  flowId: string;
  historyId: string;
}

export const useGetFlowHistoryEntry: useQueryFunctionType<
  FlowHistoryEntryParams,
  FlowVersionEntryWithData
> = ({ flowId, historyId }, options) => {
  const { query } = UseRequestProcessor();

  const getEntryFn = async (): Promise<FlowVersionEntryWithData> => {
    const response = await api.get<FlowVersionEntryWithData>(
      `${getURL("FLOWS")}/${flowId}/history/${historyId}`,
    );
    return response.data;
  };

  return query(["useGetFlowHistoryEntry", { flowId, historyId }], getEntryFn, {
    ...options,
    enabled: !!historyId && (options?.enabled ?? true),
  });
};
