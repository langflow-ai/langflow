import { useCallback, useMemo, useState } from "react";
import type { Span } from "./types";

interface UseSpanTreeParams {
  spans: Span[];
  selectedSpanId: string | null;
}

export interface UseSpanTreeReturn {
  expandedIds: Set<string>;
  focusedId: string | null;
  setFocusedId: (id: string) => void;
  toggleExpand: (spanId: string) => void;
  visibleIds: string[];
  handleTreeKeyDown: (e: React.KeyboardEvent) => void;
}

export function useSpanTree({
  spans,
  selectedSpanId,
}: UseSpanTreeParams): UseSpanTreeReturn {
  const [expandedIds, setExpandedIds] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    spans.forEach((span) => initial.add(span.id));
    return initial;
  });

  const [focusedId, setFocusedId] = useState<string | null>(
    () => selectedSpanId ?? spans[0]?.id ?? null,
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

  const allSpansMap = useMemo(() => {
    const map = new Map<string, Span>();
    const visit = (list: Span[]) => {
      for (const span of list) {
        map.set(span.id, span);
        visit(span.children);
      }
    };
    visit(spans);
    return map;
  }, [spans]);

  const parentMap = useMemo(() => {
    const map = new Map<string, string | null>();
    const visit = (list: Span[], parentId: string | null) => {
      for (const span of list) {
        map.set(span.id, parentId);
        visit(span.children, span.id);
      }
    };
    visit(spans, null);
    return map;
  }, [spans]);

  const visibleIds = useMemo(() => {
    const ids: string[] = [];
    const visit = (list: Span[]) => {
      for (const span of list) {
        ids.push(span.id);
        if (expandedIds.has(span.id) && span.children.length > 0) {
          visit(span.children);
        }
      }
    };
    visit(spans);
    return ids;
  }, [spans, expandedIds]);

  const focusNode = useCallback((id: string) => {
    setFocusedId(id);
    document
      .querySelector<HTMLElement>(`[data-testid="span-node-${id}"]`)
      ?.focus();
  }, []);

  const handleTreeKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!focusedId) return;
      const currentIndex = visibleIds.indexOf(focusedId);
      const span = allSpansMap.get(focusedId);

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const nextId = visibleIds[currentIndex + 1];
          if (nextId) focusNode(nextId);
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const prevId = visibleIds[currentIndex - 1];
          if (prevId) focusNode(prevId);
          break;
        }
        case "ArrowRight": {
          e.preventDefault();
          if (!span) break;
          if (!expandedIds.has(span.id) && span.children.length > 0) {
            toggleExpand(span.id);
          } else if (expandedIds.has(span.id) && span.children.length > 0) {
            focusNode(span.children[0].id);
          }
          break;
        }
        case "ArrowLeft": {
          e.preventDefault();
          if (!span) break;
          if (expandedIds.has(span.id) && span.children.length > 0) {
            toggleExpand(span.id);
          } else {
            const parentId = parentMap.get(span.id);
            if (parentId) focusNode(parentId);
          }
          break;
        }
      }
    },
    [
      focusedId,
      visibleIds,
      allSpansMap,
      expandedIds,
      toggleExpand,
      parentMap,
      focusNode,
    ],
  );

  return {
    expandedIds,
    focusedId,
    setFocusedId,
    toggleExpand,
    visibleIds,
    handleTreeKeyDown,
  };
}
