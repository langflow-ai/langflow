export type SpanType = "chain" | "llm" | "tool" | "retriever" | "embedding" | "parser" | "agent";

export type SpanStatus = "success" | "error" | "running";

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
  spans: Span[];
}
