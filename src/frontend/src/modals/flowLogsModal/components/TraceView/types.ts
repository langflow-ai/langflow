export type SpanType =
  | "chain"
  | "llm"
  | "tool"
  | "retriever"
  | "embedding"
  | "parser"
  | "agent"
  | "none";

export type SpanStatus = "unset" | "ok" | "error";

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cost: number;
}

export interface Span {
  id: string;
  name: string;
  type: SpanType;
  status: SpanStatus;
  startTime: string;
  endTime?: string;
  latencyMs: number;
  inputs: Record<string, unknown>;
  outputs: Record<string, unknown>;
  error?: string;
  modelName?: string;
  tokenUsage?: TokenUsage;
  children: Span[];
}

export interface Trace {
  id: string;
  name: string;
  status: SpanStatus;
  startTime: string;
  endTime?: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCost: number;
  flowId: string;
  sessionId: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  spans: Span[];
}
