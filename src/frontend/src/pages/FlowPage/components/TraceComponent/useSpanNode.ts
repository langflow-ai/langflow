import type { SpanNodeProps } from "./types";
import { useSpanNodeActions } from "./useSpanNodeActions";
import { useSpanNodeData } from "./useSpanNodeData";

export function useSpanNode({
  span,
  depth,
  isExpanded,
  onSelect,
  onToggle,
}: Pick<
  SpanNodeProps,
  "span" | "depth" | "isExpanded" | "onSelect" | "onToggle"
>) {
  const data = useSpanNodeData({ span, depth, isExpanded });
  const actions = useSpanNodeActions({
    hasChildren: data.hasChildren,
    onSelect,
    onToggle,
  });
  return { ...data, ...actions };
}
