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
