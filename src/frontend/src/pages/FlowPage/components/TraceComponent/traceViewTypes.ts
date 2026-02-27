import type { Span } from "./types";

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
