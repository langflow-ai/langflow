import { Span, Trace } from "@/modals/flowLogsModal/components/TraceView/types";
import { SpanApiResponse, TraceApiResponse } from "./types";

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
    flowId: apiTrace.flowId,
    sessionId: apiTrace.sessionId,
    input: apiTrace.input,
    output: apiTrace.output,
    spans: apiTrace.spans.map(convertSpan),
  };
}
export { sanitizeParams, sanitizeString, convertTrace, convertSpan };
