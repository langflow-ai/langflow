import type { useQueryFunctionType } from "../../../../types/api";
import type { Trace, Span } from "../../../../modals/flowLogsModal/components/TraceView/types";
import { api } from "../../api";
import { getURL } from "../../helpers/constants";
import { UseRequestProcessor } from "../../services/request-processor";

interface TraceQueryParams {
  traceId: string | null;
}

interface TraceApiResponse {
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
  spans: SpanApiResponse[];
}

interface SpanApiResponse {
  id: string;
  name: string;
  type: string;
  status: string;
  startTime: string;
  endTime?: string;
  latencyMs: number;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  error?: string;
  modelName?: string;
  tokenUsage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    cost: number;
  };
  children: SpanApiResponse[];
}

/**
 * Convert API span response to frontend Span type
 */
function convertSpan(apiSpan: SpanApiResponse): Span {
  return {
    id: apiSpan.id,
    name: apiSpan.name,
    type: apiSpan.type as Span["type"],
    status: apiSpan.status as Span["status"],
    startTime: apiSpan.startTime,
    endTime: apiSpan.endTime,
    latencyMs: apiSpan.latencyMs,
    inputs: apiSpan.inputs,
    outputs: apiSpan.outputs,
    error: apiSpan.error,
    modelName: apiSpan.modelName,
    tokenUsage: apiSpan.tokenUsage,
    children: apiSpan.children?.map(convertSpan) ?? [],
  };
}

/**
 * Convert API trace response to frontend Trace type
 */
function convertTrace(apiTrace: TraceApiResponse): Trace | null {
  if (!apiTrace.spans || apiTrace.spans.length === 0) return null;

  return {
    id: apiTrace.id,
    name: apiTrace.name,
    status: apiTrace.status as Trace["status"],
    startTime: apiTrace.startTime,
    endTime: apiTrace.endTime,
    totalLatencyMs: apiTrace.totalLatencyMs,
    totalTokens: apiTrace.totalTokens,
    totalCost: apiTrace.totalCost,
    spans: apiTrace.spans.map(convertSpan),
  };
}

export const useGetTraceQuery: useQueryFunctionType<
  TraceQueryParams,
  Trace | null
> = ({ traceId }, options) => {
  const { query } = UseRequestProcessor();

  const getTraceFn = async (): Promise<Trace | null> => {
    if (!traceId) return null;

    const result = await api.get<TraceApiResponse>(
      `${getURL("TRACES")}/${traceId}`,
    );

    return convertTrace(result.data);
  };

  const queryResult = query(
    ["useGetTraceQuery", traceId],
    getTraceFn,
    {
      refetchOnWindowFocus: false,
      enabled: !!traceId,
      ...options,
    },
  );

  return queryResult;
};
