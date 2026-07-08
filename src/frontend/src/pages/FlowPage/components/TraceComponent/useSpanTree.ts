import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
  registerNodeRef: (id: string, el: HTMLElement | null) => void;
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

  // Ref map used by focusNode so production code never touches data-testid or
  // raw CSS selectors. SpanNode registers itself here via registerNodeRef.
  const nodeRefs = useRef<Map<string, HTMLElement>>(new Map());

  const registerNodeRef = useCallback((id: string, el: HTMLElement | null) => {
    if (el) {
      nodeRefs.current.set(id, el);
    } else {
      nodeRefs.current.delete(id);
    }
  }, []);

  // Refs let the reconciliation effects read current values without making
  // them trigger re-runs they shouldn't own.
  const spansRef = useRef(spans);
  spansRef.current = spans;
  const selectedSpanIdRef = useRef(selectedSpanId);
  selectedSpanIdRef.current = selectedSpanId;

  // Stable string that changes only when the set of span IDs changes (new trace).
  const spansKey = useMemo(() => {
    const ids: string[] = [];
    const visit = (list: Span[]) => {
      for (const s of list) {
        ids.push(s.id);
        visit(s.children);
      }
    };
    visit(spans);
    return ids.join("\0");
  }, [spans]);

  // Reset expanded/focused state when the tree identity changes (different trace).
  // Functional setters bail out without a re-render when the computed value
  // matches what is already in state (covers the initial-render case).
  useEffect(() => {
    const next = new Set<string>();
    const visit = (list: Span[]) => {
      for (const s of list) {
        next.add(s.id);
        visit(s.children);
      }
    };
    visit(spansRef.current);
    setExpandedIds((prev) => {
      const hasNew = [...next].some((id) => !prev.has(id));
      const hasMissing = [...prev].some((id) => !next.has(id));
      return hasNew || hasMissing ? next : prev;
    });
    setFocusedId((prev) => {
      const want = selectedSpanIdRef.current ?? spansRef.current[0]?.id ?? null;
      return prev === want ? prev : want;
    });
  }, [spansKey]);

  // Clamp focus when selectedSpanId changes within the same trace.
  useEffect(() => {
    setFocusedId(selectedSpanId ?? spansRef.current[0]?.id ?? null);
  }, [selectedSpanId]);

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
    nodeRefs.current.get(id)?.focus();
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
    registerNodeRef,
  };
}
