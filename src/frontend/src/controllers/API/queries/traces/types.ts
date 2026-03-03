import { Span } from "@/pages/FlowPage/components/TraceComponent/types";

export interface TracesQueryParams {
  flowId: string | null;
  sessionId?: string | null;
  params?: Record<string, unknown>;
}

export interface TraceListItem {
  id: string;
  name: string;
  status: Span["status"];
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

export interface TracesResponse {
  traces: TraceListItem[];
  total: number;
  pages?: number;
}

export interface TraceQueryParams {
  traceId: string | null;
}

export interface TraceApiResponse {
  id: string;
  name: string;
  status: string;
  startTime: string;
  endTime?: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCost: number;
  flowId: string;
  sessionId: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  spans: SpanApiResponse[];
}

export interface SpanApiResponse {
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
