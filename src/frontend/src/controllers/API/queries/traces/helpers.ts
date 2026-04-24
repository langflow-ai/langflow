import {
  Span,
  SpanStatus,
  SpanType,
  Trace,
} from "@/pages/FlowPage/components/TraceComponent/types";
import { SpanApiResponse, TraceApiResponse } from "./types";

const VALID_SPAN_TYPES: ReadonlySet<SpanType> = new Set<SpanType>([
  "chain",
  "llm",
  "tool",
  "retriever",
  "embedding",
  "parser",
  "agent",
  "none",
]);

const VALID_SPAN_STATUSES: ReadonlySet<SpanStatus> = new Set<SpanStatus>([
  "unset",
  "ok",
  "error",
]);

export function parseSpanType(value: string): SpanType {
  return VALID_SPAN_TYPES.has(value as SpanType) ? (value as SpanType) : "none";
}

export function parseSpanStatus(value: string): SpanStatus {
  return VALID_SPAN_STATUSES.has(value as SpanStatus)
    ? (value as SpanStatus)
    : "unset";
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

function convertSpan(apiSpan: SpanApiResponse): Span {
  return {
    id: apiSpan.id,
    name: apiSpan.name,
    type: parseSpanType(apiSpan.type),
    status: parseSpanStatus(apiSpan.status),
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
    status: parseSpanStatus(apiTrace.status),
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
