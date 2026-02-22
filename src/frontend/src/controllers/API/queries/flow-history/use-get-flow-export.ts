import type { useQueryFunctionType } from "@/types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface FlowExportParams {
  flowId: string;
  includeHistory?: boolean;
}

export const useGetFlowExport: useQueryFunctionType<
  FlowExportParams,
  Record<string, unknown>
> = ({ flowId, includeHistory = true }, options) => {
  const { query } = UseRequestProcessor();

  const getExportFn = async (): Promise<Record<string, unknown>> => {
    const response = await api.get<Record<string, unknown>>(
      `${getURL("FLOWS")}/${flowId}/history/export`,
      { params: { include_history: includeHistory } },
    );
    return response.data;
  };

  return query(
    ["useGetFlowExport", { flowId, includeHistory }],
    getExportFn,
    { enabled: false, ...options },
  );
};
