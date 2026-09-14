import { Loader2 } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useStickToBottomContext } from "use-stick-to-bottom";

// Placed inside StickToBottom so useStickToBottomContext is available
export const LoadMoreTrigger = ({
  hasMore,
  isLoadingMore,
  onLoadMore,
}: {
  hasMore: boolean;
  isLoadingMore: boolean;
  onLoadMore: () => Promise<number>;
}) => {
  const { scrollRef } = useStickToBottomContext();
  const sentinelRef = useRef<HTMLDivElement>(null);
  // Actual scroll element. stick-to-bottom's scrollRef can be a full-height,
  // non-scrolling element (an ancestor scrolls instead); using it as the
  // observer root makes the sentinel intersect permanently and kills paging.
  const containerRef = useRef<HTMLElement | null>(null);
  // Load-in-progress guard (ref, so chained loads don't wait on state).
  const loadingRef = useRef(false);
  // Armed only after the list overflows and has landed at the bottom once,
  // so the sentinel being visible during open doesn't cascade-load history.
  const armedRef = useRef(false);

  // Keep stable refs to avoid recreating the observer on every render
  const hasMoreRef = useRef(hasMore);
  hasMoreRef.current = hasMore;
  const onLoadMoreRef = useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;

  // Load a page, then restore scrollTop so the prepended messages push the
  // sentinel out of view — otherwise the observer never re-fires (no
  // intersection transition) and pagination deadlocks after one page.
  const runLoad = useCallback(async () => {
    const container = containerRef.current;
    const sentinel = sentinelRef.current;
    if (
      !container ||
      !sentinel ||
      loadingRef.current ||
      !hasMoreRef.current ||
      !armedRef.current
    ) {
      return;
    }

    // Drop stale observer entries (e.g. delivered after the initial pin).
    {
      const cRect = container.getBoundingClientRect();
      const sRect = sentinel.getBoundingClientRect();
      const sentinelVisible =
        sRect.bottom >= cRect.top && sRect.top <= cRect.bottom;
      if (!sentinelVisible) {
        return;
      }
    }

    loadingRef.current = true;
    try {
      const prevHeight = container.scrollHeight;
      const prevTop = container.scrollTop;

      const loaded = await onLoadMoreRef.current();

      if (loaded > 0) {
        // Wait for the prepended nodes to be committed before measuring.
        await new Promise<void>((resolve) => {
          requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
        });
        const delta = container.scrollHeight - prevHeight;
        container.scrollTop = prevTop + delta;

        // Chain another load if the sentinel is still visible (short pages).
        const cRect = container.getBoundingClientRect();
        const sRect = sentinel.getBoundingClientRect();
        if (
          sRect.bottom >= cRect.top &&
          sRect.top <= cRect.bottom &&
          hasMoreRef.current
        ) {
          loadingRef.current = false;
          void runLoad();
          return;
        }
      }
    } finally {
      loadingRef.current = false;
    }
  }, []);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    // Nearest ancestor that is scrollable AND actually clipping; ancestors
    // with overflow-y:auto but full content height never scroll. Fall back
    // to the first overflow-styled ancestor, then scrollRef.
    let clipping: HTMLElement | null = null;
    let styled: HTMLElement | null = null;
    let parent: HTMLElement | null = sentinel.parentElement;
    while (parent) {
      const { overflowY } = getComputedStyle(parent);
      if (
        overflowY === "auto" ||
        overflowY === "scroll" ||
        overflowY === "overlay"
      ) {
        styled = styled ?? parent;
        if (parent.scrollHeight > parent.clientHeight + 1) {
          clipping = parent;
          break;
        }
      }
      parent = parent.parentElement;
    }
    const container = clipping ?? styled ?? scrollRef.current;
    if (!container) return;
    containerRef.current = container;

    const checkArmed = () => {
      if (armedRef.current) return;
      const hasOverflow = container.scrollHeight > container.clientHeight;
      const atBottom =
        container.scrollTop + container.clientHeight >=
        container.scrollHeight - 2;
      if (hasOverflow && atBottom) {
        armedRef.current = true;
      }
    };
    checkArmed();
    container.addEventListener("scroll", checkArmed, { passive: true });

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          void runLoad();
        }
      },
      { root: container, threshold: 0 },
    );
    observer.observe(sentinel);

    return () => {
      container.removeEventListener("scroll", checkArmed);
      observer.disconnect();
    };
  }, [scrollRef, runLoad]);

  if (!hasMore) return null;

  return (
    <div
      ref={sentinelRef}
      className="flex h-8 w-full items-center justify-center"
    >
      {isLoadingMore && (
        <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
      )}
    </div>
  );
};
