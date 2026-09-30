import { useEffect } from "react";

/**
 * `:not([role])` keeps the pass idempotent and leaves ReactFlow's own
 * `<svg class="react-flow__marker">` — which already ships `aria-hidden` — and
 * any future roled wrapper untouched.
 */
const UNROLED_EDGE_SVG = ".react-flow__edges > svg:not([role])";

/**
 * Marks ReactFlow's per-edge `<svg>` wrappers as presentational.
 *
 * ReactFlow renders one bare `<svg style="z-index:…">` per edge and gives us no
 * prop hook for it: the per-edge `domAttributes` escape hatch lands on the
 * inner `<g>`, not on the wrapper. IBM Equal Access therefore reports each
 * wrapper as an unnamed graphic (`svg_graphics_labelled`, WCAG 1.1.1). The
 * wrappers carry no meaning of their own, so `role="presentation"` is the
 * correct answer — it drops the wrapper's implicit `graphics-document` role
 * without touching anything inside it.
 *
 * Do NOT reach for `aria-hidden` here. The named, tabbable widget `<g>` (role="button")
 * that carries the edge's accessible name lives *inside* each wrapper, so an
 * `aria-hidden` ancestor would erase every edge name and pull the edges out of
 * the accessibility tree entirely.
 *
 * @param canvasRef Element wrapping the ReactFlow canvas.
 */
export function usePresentationalEdgeSvgs(
  canvasRef: React.RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const markEdgeSvgs = () => {
      for (const svg of canvas.querySelectorAll(UNROLED_EDGE_SVG)) {
        svg.setAttribute("role", "presentation");
      }
    };

    // Edges mount, unmount and re-mount for the lifetime of the canvas, so a
    // one-shot pass on mount would only cover the edges present at that moment.
    markEdgeSvgs();
    const observer = new MutationObserver(markEdgeSvgs);
    observer.observe(canvas, { childList: true, subtree: true });

    return () => observer.disconnect();
  }, [canvasRef]);
}
