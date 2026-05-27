import { useEffect } from "react";

/**
 * Suppresses text selection during any canvas drag in WKWebView.
 *
 * WKWebView does not suppress selection on pointer-drag the way Chromium does,
 * so ace editors, labels, and inputs highlight as the pointer moves over them.
 * We set user-select:none on the root element for the lifetime of the drag and
 * restore it on mouseup — so normal text editing is completely unaffected.
 *
 * Applies to all mousedown events on the canvas (shift-drag box-select,
 * edge dragging, node dragging) not just shift-drag.
 */
export function useCanvasDragSelectFix(
  ref: React.RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const onMouseDown = () => {
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
