/**
 * Visibility state inputs for an input (target / left-side) handle.
 *
 * Input handles render as a small collapsed dot by default to keep the canvas
 * clean, and grow to full size when any of the reveal flags below is true.
 * Output (source) handles are never affected by this rule.
 */
export interface InputHandleVisibilityState {
  /** Whether this is an input (target/left) handle. Output handles never collapse. */
  left: boolean;
  /** The handle itself is hovered. */
  isHovered: boolean;
  /** The node owning this handle is selected (clicking a node selects it). */
  selected: boolean;
  /** An edge is connected to this handle. */
  hasConnectedEdge: boolean;
  /** A connection drag or filter is active anywhere on the canvas. */
  filterPresent: boolean;
  /** The node is in model connection mode ("Connect other models"). */
  isInConnectionMode: boolean;
}

/**
 * Decide whether an input handle should render in its collapsed (small) state.
 *
 * Returns `true` only for input handles that nothing currently reveals.
 * Output handles always return `false` (they keep their normal size).
 */
export function isInputHandleCollapsed(
  state: InputHandleVisibilityState,
): boolean {
  if (!state.left) {
    return false;
  }

  const isRevealed =
    state.isHovered ||
    state.selected ||
    state.hasConnectedEdge ||
    state.filterPresent ||
    state.isInConnectionMode;

  return !isRevealed;
}
