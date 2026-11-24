import type { FitViewOptions } from "@xyflow/react";

export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 2;

/**
 * Padding kept around the graph when fitting the canvas. The top allowance
 * clears the floating toolbar; the sides are symmetric unless the inspection
 * panel is open over the right edge.
 */
export const FIT_VIEW_PADDING = {
  left: "20px",
  right: "20px",
  top: "80px",
} as const;

/** Padding to use while the inspection panel covers the right of the canvas. */
export const FIT_VIEW_PADDING_WITH_INSPECTION_PANEL = {
  ...FIT_VIEW_PADDING,
  right: "340px",
} as const;

/**
 * Single source of truth for how the canvas fits the graph, shared by the
 * initial fit and the Zoom to Fit control so opening a flow lands on exactly
 * the viewport the shortcut produces.
 */
export const FIT_VIEW_OPTIONS: FitViewOptions = {
  minZoom: MIN_ZOOM,
  maxZoom: MAX_ZOOM,
  padding: FIT_VIEW_PADDING,
};
