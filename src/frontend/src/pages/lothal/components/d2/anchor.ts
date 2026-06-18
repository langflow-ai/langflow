// Click-to-anchor resolution over a D2-rendered SVG (Epic D.6).
//
// D2 bakes each element's source id into the SVG as a base64-encoded CSS class
// on the shape/connection group. Given a clicked DOM element we walk up to the
// SVG root, decode those classes, and resolve the nearest node or edge into a
// stable, collision-safe `Anchor` — the reference the chat composer (D.7) drops
// inline so the LLM gets an exact handle on what the user means.
//
// Lifted from the browser-verified spike (scratchpad/d2-reference): duplicate-
// label nodes resolve to distinct ids, parallel edges disambiguate via `#index`,
// and a sequence message anchors by its label ("POST /sync"), not the src→dst
// relation.

export interface Anchor {
  kind: "node" | "edge";
  /** Stable, collision-safe handle for the element (what the LLM receives). */
  id: string;
  /** Human-facing label (node text, or the edge message / "src → dst"). */
  label: string;
  src?: string;
  dst?: string;
  /** Which edge among parallel src→dst connections (0-based). */
  index?: number;
}

/** Decode a D2 base64 element-id class (UTF-8 safe). `null` if it isn't one. */
export function decodeElementId(s: string): string | null {
  try {
    return decodeURIComponent(escape(window.atob(s)));
  } catch {
    return null;
  }
}

/**
 * Resolve the D2 element under `target` (walking up to `root`) into an `Anchor`,
 * or `null` when the click didn't land on a diagram element. An edge wins over a
 * node (the connection group nests the shapes it touches).
 */
export function resolveAnchor(target: Element, root: Element): Anchor | null {
  let el: Element | null = target;
  let edge: string | null = null;
  let edgeEl: Element | null = null;
  let node: string | null = null;

  while (el && el !== root) {
    el.classList?.forEach((c) => {
      // D2 ids are base64; skip ordinary class names cheaply before decoding.
      if (c.length >= 4 && /^[A-Za-z0-9+/]+={0,2}$/.test(c)) {
        const d = decodeElementId(c);
        if (!d) return;
        if (/-&gt;|->/.test(d)) {
          if (!edge) {
            edge = d;
            edgeEl = el;
          }
        } else if (/^[\w.-]+$/.test(d)) {
          node = node ?? d;
        }
      }
    });
    el = el.parentElement;
  }

  if (edge) {
    const m = (edge as string)
      .replace(/&gt;/g, ">")
      .match(/([\w.-]+)\s*->\s*([\w.-]+)/);
    if (m) {
      // Prefer the message LABEL (e.g. "POST /sync") over the "src → dst"
      // relation: D2 puts the base64 id on the connection group, which contains
      // the label <text>, so read it from within that group.
      const txt = (edgeEl as Element | null)
        ?.querySelector?.("text")
        ?.textContent?.trim();
      const label = txt || `${m[1]} → ${m[2]}`;
      // D2 disambiguates parallel edges with a [index]; keep it so two edges
      // between the same pair don't collapse to one anchor.
      const idxM = (edge as string).match(/\)\[(\d+)\]/);
      const index = idxM ? parseInt(idxM[1], 10) : 0;
      const id =
        index > 0 ? `${m[1]} → ${m[2]} #${index + 1}` : `${m[1]} → ${m[2]}`;
      return { kind: "edge", id, label, src: m[1], dst: m[2], index };
    }
  }
  if (node) return { kind: "node", id: node, label: node };
  return null;
}
