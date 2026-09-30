import {
  NOTE_NODE_MIN_HEIGHT,
  NOTE_NODE_MIN_WIDTH,
} from "@/constants/constants";

const NOTE_ABOVE_TOOLBAR_GAP = 16;

/**
 * Computes the screen-space top-left coordinate to pass to
 * `reactFlowInstance.screenToFlowPosition` when placing a new note above the
 * canvas toolbar. Falls back to the viewport centre when the toolbar element
 * cannot be found.
 */
export function computeNoteScreenPosition(
  toolbarRect: DOMRect | null | undefined,
): { x: number; y: number } {
  const screenX = toolbarRect
    ? toolbarRect.left + toolbarRect.width / 2
    : window.innerWidth / 2;
  const screenY = toolbarRect
    ? toolbarRect.top - NOTE_NODE_MIN_HEIGHT - NOTE_ABOVE_TOOLBAR_GAP
    : window.innerHeight / 2;

  return {
    x: screenX - NOTE_NODE_MIN_WIDTH / 2,
    y: screenY,
  };
}
