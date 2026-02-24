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
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
}

interface TracesResponse {
  traces: TraceListItem[];
  total: number;
  pages?: number;
}

const sanitizeString = (value: string, maxLen = 50) => {
  const filtered = Array.from(value)
    .filter((ch) => {
      const code = ch.charCodeAt(0);
      return code >= 32 && code !== 127;
    })
    .join("");

  return filtered.trim().slice(0, maxLen);
};

const sanitizeParams = (input: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(input).map(([key, value]) => {
      if (typeof value === "string") {
        return [key, sanitizeString(value)];
      }
      return [key, value];
    }),
  );

export const useGetTracesQuery: useQueryFunctionType<
  TracesQueryParams,
  TracesResponse
> = ({ flowId, sessionId, params }, options) => {
  const { query } = UseRequestProcessor();

  const getTracesFn = async (): Promise<TracesResponse> => {
    if (!flowId) return { traces: [], total: 0 };

    const config: { params: Record<string, unknown> } = {
      params: { flow_id: sanitizeString(flowId) },
    };

    if (sessionId) {
      config.params.session_id = sanitizeString(sessionId);
    }

    if (params) {
      config.params = sanitizeParams({ ...config.params, ...params });
    }

    const result = await api.get<TracesResponse>(`${getURL("TRACES")}`, config);

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
