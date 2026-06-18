// The live diagram surface (Epic D.6). Replaces the xyflow <DiagramCanvas> on
// the Lothal canvas path: the diagram is D2 source now, the backend renders it
// to SVG (D.3/D.6) and we just display that SVG — pannable, zoomable, with a
// thin click-to-anchor layer over D2's baked-in element ids. No @xyflow/react,
// no D2 compiler in the browser.
//
// Double-clicking a box or arrow resolves the D2 element under the cursor and
// hands it to `onAnchor` (the chat composer wires this up in D.7); without a
// handler the layer is inert. Panning is pointer-drag; zooming is the wheel or
// the corner controls.

import DOMPurify from "dompurify";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Anchor } from "./d2/anchor";
import { resolveAnchor } from "./d2/anchor";

const MIN_SCALE = 0.2;
const MAX_SCALE = 4;
const ZOOM_STEP = 1.2;

const clampScale = (s: number) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, s));

export function D2Canvas({
  svg,
  onAnchor,
}: {
  /** Server-rendered D2 SVG markup (`DiagramResponse.svg`). */
  svg: string;
  /** Called with the resolved element when a box/arrow is double-clicked. */
  onAnchor?: (anchor: Anchor) => void;
}) {
  // The SVG is server-rendered from LLM-authored D2, so treat it as untrusted
  // before injecting it: sanitize to the SVG profile and drop the script /
  // foreignObject vectors. D2's diagram output is plain SVG shapes + <text>, so
  // this preserves the rendered markup (and the base64 anchor classes / viewBox
  // we read back) while neutralising any injected scripting.
  const safeSvg = useMemo(
    () =>
      DOMPurify.sanitize(svg, {
        USE_PROFILES: { svg: true, svgFilters: true },
        FORBID_TAGS: ["script", "foreignObject"],
      }),
    [svg],
  );
  const viewport = useRef<HTMLDivElement>(null);
  const holder = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState({ scale: 1, x: 0, y: 0 });
  // The diagram's natural size, read from the SVG's viewBox. D2's SVG carries a
  // viewBox but no width/height, so it would collapse to 0×0; we size the holder
  // to this and let the SVG fill it (CSS), which survives re-renders — unlike
  // mutating width/height on the injected DOM, which React reconciliation wipes.
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  // Mirror the latest transform so pointer handlers read it without re-binding.
  const transformRef = useRef(transform);
  transformRef.current = transform;
  const drag = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    originX: number;
    originY: number;
  } | null>(null);

  useLayoutEffect(() => {
    const vb = holder.current?.querySelector("svg")?.getAttribute("viewBox");
    const p = vb?.split(/\s+/).map(Number);
    if (p && p.length === 4 && p[2] > 0 && p[3] > 0) {
      setNatural({ w: p[2], h: p[3] });
    } else {
      setNatural(null);
    }
  }, [svg]);

  // Fit the freshly-measured diagram into the viewport (scaled down if it's
  // bigger), centred. Guarded for jsdom, where layout boxes are all zero.
  useLayoutEffect(() => {
    const view = viewport.current;
    if (!view || !natural) return;
    const vw = view.clientWidth;
    const vh = view.clientHeight;
    if (!vw || !vh) return;
    const scale = clampScale(
      Math.min(1, (vw - 32) / natural.w, (vh - 32) / natural.h),
    );
    setTransform({
      scale,
      x: (vw - natural.w * scale) / 2,
      y: (vh - natural.h * scale) / 2,
    });
  }, [natural]);

  const zoomBy = useCallback((factor: number, cx?: number, cy?: number) => {
    const view = viewport.current;
    setTransform((t) => {
      const next = clampScale(t.scale * factor);
      if (next === t.scale) return t;
      // Keep the point under the cursor (or the viewport centre) fixed.
      const rect = view?.getBoundingClientRect();
      const px = cx ?? (rect ? rect.width / 2 : 0);
      const py = cy ?? (rect ? rect.height / 2 : 0);
      const k = next / t.scale;
      return {
        scale: next,
        x: px - (px - t.x) * k,
        y: py - (py - t.y) * k,
      };
    });
  }, []);

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    if (e.button !== 0) return;
    drag.current = {
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      originX: transformRef.current.x,
      originY: transformRef.current.y,
    };
    e.currentTarget.setPointerCapture?.(e.pointerId);
  }, []);

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || d.pointerId !== e.pointerId) return;
    setTransform((t) => ({
      ...t,
      x: d.originX + (e.clientX - d.startX),
      y: d.originY + (e.clientY - d.startY),
    }));
  }, []);

  const endDrag = useCallback((e: React.PointerEvent) => {
    if (drag.current?.pointerId === e.pointerId) {
      drag.current = null;
      e.currentTarget.releasePointerCapture?.(e.pointerId);
    }
  }, []);

  const onDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      if (!holder.current || !onAnchor) return;
      // The pan gesture captures the pointer (setPointerCapture), which retargets
      // the compatibility mouse events — so `e.target` is this viewport div, not
      // the diagram shape under the cursor. Hit-test by geometry instead to find
      // the real SVG element the user double-clicked (guarded for jsdom, which
      // has no elementFromPoint; there `e.target` is already the shape).
      const hit =
        typeof document.elementFromPoint === "function"
          ? document.elementFromPoint(e.clientX, e.clientY)
          : null;
      const target = hit ?? (e.target as Element);
      const anchor = resolveAnchor(target, holder.current);
      if (anchor) onAnchor(anchor);
    },
    [onAnchor],
  );

  // Native wheel listeners are passive by default, so a React onWheel can't
  // preventDefault the page from scrolling under us. Attach non-passively.
  useEffect(() => {
    const view = viewport.current;
    if (!view) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      const rect = view.getBoundingClientRect();
      zoomBy(
        e.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP,
        e.clientX - rect.left,
        e.clientY - rect.top,
      );
    };
    view.addEventListener("wheel", handler, { passive: false });
    return () => view.removeEventListener("wheel", handler);
  }, [zoomBy]);

  return (
    // The canvas is an inherently pointer-driven surface (pan/zoom over an SVG);
    // zooming is also reachable via the labelled buttons below.
    // biome-ignore lint/a11y/noStaticElementInteractions: pannable diagram surface
    <div
      ref={viewport}
      className="lothal-d2-canvas"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={endDrag}
      onPointerCancel={endDrag}
      onDoubleClick={onDoubleClick}
    >
      <div
        ref={holder}
        className="lothal-d2-holder"
        style={{
          width: natural ? `${natural.w}px` : undefined,
          height: natural ? `${natural.h}px` : undefined,
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.scale})`,
        }}
        dangerouslySetInnerHTML={{ __html: safeSvg }}
      />
      <div className="lothal-d2-controls">
        <button
          type="button"
          aria-label="Zoom in"
          onClick={() => zoomBy(ZOOM_STEP)}
        >
          +
        </button>
        <button
          type="button"
          aria-label="Zoom out"
          onClick={() => zoomBy(1 / ZOOM_STEP)}
        >
          −
        </button>
      </div>
    </div>
  );
}
