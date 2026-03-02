import { CellClickedEvent } from "ag-grid-community";
import { TraceListItem } from "@/controllers/API/queries/traces/types";
import { createFlowTracesColumns } from "./config/flowTraceColumns";

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

export interface SpanNodeProps {
  span: Span;
  depth: number;
  isExpanded: boolean;
  isSelected: boolean;
  onToggle: () => void;
  onSelect: () => void;
}

export interface SpanDetailProps {
  span: Span | null;
}

export interface TraceViewProps {
  flowId?: string | null;
  initialTraceId?: string | null;
  onTraceClick?: (traceId: string) => void;
}

export interface TraceDetailViewProps {
  traceId: string | null;
  flowName?: string | null;
}

export interface TraceAccordionItemProps {
  traceId: string;
  traceName: string;
  traceStatus: string;
  traceStartTime: string;
  totalLatencyMs: number;
  totalTokens: number;
  totalCost: number;
  sessionId: string;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  isExpanded: boolean;
  onTraceClick?: (traceId: string) => void;
}

export type StatusIconProps = {
  colorClass: string;
  iconName: "Loader2" | "CircleCheck" | "CircleX";
  shouldSpin: boolean;
};

export type RenderGroupedSessionType = {
  isLoading: boolean;
  groupedRows: Array<[string, TraceListItem[]]>;
  columns: ReturnType<typeof createFlowTracesColumns>;
  expandedSessionIds: string[];
  handleCellClicked: (event: CellClickedEvent) => void;
};

export type DateRangePopoverProps = {
  startDate: string;
  endDate: string;
  onStartDateChange: (value: string) => void;
  onEndDateChange: (value: string) => void;
};
