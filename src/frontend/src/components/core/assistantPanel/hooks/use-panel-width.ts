import { useEffect, useState } from "react";

/**
 * Tracks the width of a DOM element using ResizeObserver.
 * Used to switch between tab bar and dropdown modes in the assistant header.
 */
export function usePanelWidth(
  ref: React.RefObject<HTMLElement | null>,
): number {
  const [width, setWidth] = useState(() => ref.current?.clientWidth ?? 0);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Set initial width immediately
    setWidth(el.clientWidth);

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setWidth(entry.contentRect.width);
      }
    });

    observer.observe(el);
    return () => observer.disconnect();
  }, [ref]);

  return width;
}
