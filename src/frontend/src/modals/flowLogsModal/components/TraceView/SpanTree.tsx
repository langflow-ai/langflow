import { useCallback, useState } from "react";
import type { Span } from "./types";
import { SpanNode } from "./SpanNode";

interface SpanTreeProps {
  spans: Span[];
  selectedSpanId: string | null;
  onSelectSpan: (span: Span) => void;
}

/**
 * Recursive tree component for rendering hierarchical spans
 * Manages expand/collapse state for each node
 */
export function SpanTree({
  spans,
  selectedSpanId,
  onSelectSpan,
}: SpanTreeProps) {
  // Track which spans are expanded (default: root level expanded)
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    // Expand root level spans by default
    spans.forEach((span) => initial.add(span.id));
    return initial;
  });

  const toggleExpand = useCallback((spanId: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(spanId)) {
        next.delete(spanId);
      } else {
        next.add(spanId);
      }
      return next;
    });
  }, []);

  /**
   * Recursively render span nodes
   */
  const renderSpan = useCallback(
    (span: Span, depth: number) => {
      const isExpanded = expandedIds.has(span.id);
      const isSelected = span.id === selectedSpanId;

      return (
        <div key={span.id} role="group">
          <SpanNode
            span={span}
            depth={depth}
            isExpanded={isExpanded}
            isSelected={isSelected}
            onToggle={() => toggleExpand(span.id)}
            onSelect={() => onSelectSpan(span)}
          />
          {isExpanded &&
            span.children.map((child) => renderSpan(child, depth + 1))}
        </div>
      );
    },
    [expandedIds, selectedSpanId, toggleExpand, onSelectSpan],
  );

  return (
    <div className="flex flex-col" role="tree" aria-label="Trace spans">
      {spans.map((span) => renderSpan(span, 0))}
    </div>
  );
}
