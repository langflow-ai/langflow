import { useEffect } from "react";

/**
 * Suppresses text selection during shift-drag in WKWebView.
 *
 * WKWebView does not suppress selection on pointer-drag the way Chromium does,
 * so ace editors, labels, and inputs highlight as the pointer moves over them.
 * We set user-select:none on the root element for the lifetime of the drag and
 * restore it on mouseup — so normal text editing is completely unaffected.
 */
export function useShiftDragSelectFix(
  ref: React.RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onMouseDown = (e: MouseEvent) => {
      if (!e.shiftKey) return;
      document.documentElement.style.setProperty("-webkit-user-select", "none");
      document.documentElement.style.setProperty("user-select", "none");
      const restore = () => {
        document.documentElement.style.removeProperty("-webkit-user-select");
        document.documentElement.style.removeProperty("user-select");
        document.removeEventListener("mouseup", restore);
      };
      document.addEventListener("mouseup", restore);
    };

    el.addEventListener("mousedown", onMouseDown);
    return () => el.removeEventListener("mousedown", onMouseDown);
  }, [ref]);
}
