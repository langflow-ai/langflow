import { keepPreviousData } from "@tanstack/react-query";
import type { useQueryFunctionType } from "../../../../types/api";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TracesQueryParams {
  flowId: string | null;
  sessionId?: string | null;
  params?: Record<string, unknown>;
}

interface TraceListItem {
  id: string;
  name: string;
  status: string;
  startTime: string;
  endTime?: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCost: number;
  flowId: string;
  sessionId?: string;
}

interface TracesResponse {
  traces: TraceListItem[];
  total: number;
}

export const useGetTracesQuery: useQueryFunctionType<
  TracesQueryParams,
  TracesResponse
> = ({ flowId, sessionId, params }, options) => {
  const { query } = UseRequestProcessor();

  const getTracesFn = async (): Promise<TracesResponse> => {
    if (!flowId) return { traces: [], total: 0 };

    const config: { params: Record<string, unknown> } = {
      params: { flow_id: flowId },
    };

    if (sessionId) {
      config.params.session_id = sessionId;
    }

    if (params) {
      config.params = { ...config.params, ...params };
    }

    const result = await api.get<TracesResponse>(
      `${getURL("TRACES")}`,
      config,
    );

    return result.data;
  };

  const queryResult = query(
    ["useGetTracesQuery", flowId, sessionId, { ...params }],
    getTracesFn,
    {
      placeholderData: keepPreviousData,
      refetchOnWindowFocus: false,
      ...options,
    },
  );

  return queryResult;
};
