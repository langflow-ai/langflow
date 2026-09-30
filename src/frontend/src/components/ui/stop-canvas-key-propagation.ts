import type { KeyboardEventHandler } from "react";

/**
 * Keys React Flow consumes on a focused node or edge: `elementSelectionKeys`
 * (Enter/Space/Escape — select and unselect) plus the arrow keys (move a
 * selected node). Mirrors `elementSelectionKeys` in @xyflow/system and
 * `arrowKeyDiffs` in @xyflow/react; revisit when upgrading React Flow.
 */
const CANVAS_RESERVED_KEYS = new Set([
  "Enter",
  " ",
  "Escape",
  "ArrowUp",
  "ArrowDown",
  "ArrowLeft",
  "ArrowRight",
]);

/**
 * Wraps a keydown handler for Radix content rendered *without* a portal, so the
 * keys React Flow reserves stop at the menu instead of reaching the canvas.
 *
 * Inline content stays in the React tree of whatever renders it, which on the
 * canvas means React Flow's node wrapper — and that wrapper listens for arrow
 * and selection keys on the node element itself. Radix consumes those keys for
 * its own roving focus but lets them keep bubbling, so without this a single
 * arrow press both navigates the menu and moves the node underneath it.
 *
 * Only propagation is stopped, never the default: Radix composes this handler
 * ahead of its own and skips its own once `defaultPrevented` is set, and its
 * Escape-to-dismiss listens on the document in the capture phase, so both keep
 * working.
 */
export function stopCanvasKeyPropagation<T extends Element>(
  handler?: KeyboardEventHandler<T>,
): KeyboardEventHandler<T> {
  return (event) => {
    handler?.(event);
    if (CANVAS_RESERVED_KEYS.has(event.key)) {
      event.stopPropagation();
    }
  };
}
