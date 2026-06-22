import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { SpanNode } from "./SpanNode";
import type { Span } from "./types";
import { useSpanTree } from "./useSpanTree";

interface SpanTreeProps {
  spans: Span[];
  selectedSpanId: string | null;
  onSelectSpan: (span: Span) => void;
}

export function SpanTree({
  spans,
  selectedSpanId,
  onSelectSpan,
}: SpanTreeProps) {
  const { t } = useTranslation();
  const {
    expandedIds,
    focusedId,
    setFocusedId,
    toggleExpand,
    handleTreeKeyDown,
  } = useSpanTree({ spans, selectedSpanId });

  const renderSpan = useCallback(
    (span: Span, depth: number, posInSet: number, setSize: number) => {
      const isExpanded = expandedIds.has(span.id);
      const isSelected = span.id === selectedSpanId;

      return (
        <div key={span.id}>
          <SpanNode
            span={span}
            depth={depth}
            isExpanded={isExpanded}
            isSelected={isSelected}
            tabIndex={focusedId === span.id ? 0 : -1}
            posInSet={posInSet}
            setSize={setSize}
            onToggle={() => toggleExpand(span.id)}
            onSelect={() => {
              setFocusedId(span.id);
              onSelectSpan(span);
            }}
          />
          {isExpanded && span.children.length > 0 && (
            <div role="group">
              {span.children.map((child, idx) =>
                renderSpan(child, depth + 1, idx + 1, span.children.length),
              )}
            </div>
          )}
        </div>
      );
    },
    [expandedIds, selectedSpanId, focusedId, toggleExpand, setFocusedId, onSelectSpan],
  );

  return (
    <div
      className="flex flex-col"
      role="tree"
      aria-label={t("trace.spanTree")}
      data-testid="span-tree"
      onKeyDown={handleTreeKeyDown}
    >
      {spans.map((span, idx) =>
        renderSpan(span, 0, idx + 1, spans.length),
      )}
    </div>
  );
}
