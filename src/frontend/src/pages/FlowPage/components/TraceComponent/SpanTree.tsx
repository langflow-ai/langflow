import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { SpanNode } from "./SpanNode";
import type { Span } from "./types";

interface SpanTreeProps {
  spans: Span[];
  selectedSpanId: string | null;
  onSelectSpan: (span: Span) => void;
}

const LOOP_ITERATION_NAME = /^Iteration \d+ \/ \d+$/;

function getInitiallyExpandedIds(spans: Span[]): Set<string> {
  const expanded = new Set<string>();

  const visit = (span: Span, isRoot = false) => {
    if (isRoot) expanded.add(span.id);
    const iterationChildren = span.children.filter((child) =>
      LOOP_ITERATION_NAME.test(child.name),
    );
    if (iterationChildren.length > 0) {
      expanded.add(span.id);
      iterationChildren.forEach((iteration) => expanded.add(iteration.id));
    }
    span.children.forEach((child) => visit(child));
  };

  spans.forEach((span) => visit(span, true));
  return expanded;
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
  const { t } = useTranslation();
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() =>
    getInitiallyExpandedIds(spans),
  );

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
    <div
      className="flex flex-col"
      role="tree"
      aria-label={t("trace.spanTree")}
      data-testid="span-tree"
    >
      {spans.map((span) => renderSpan(span, 0))}
    </div>
  );
}
