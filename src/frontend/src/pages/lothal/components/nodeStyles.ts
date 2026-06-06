// Shared bits for the lothal canvas node types (actorNode / systemNode), so the
// two stay visually and structurally identical.

// The data both custom nodes carry. A `type` (not an `interface`) so it stays
// assignable to xyflow's `Record<string, unknown>` node-data constraint.
export type CanvasNodeData = {
  label?: string;
  note?: string;
};

// Small borderless accent dots for the left/right message handles.
export const HANDLE_STYLE = {
  width: 7,
  height: 7,
  background: "var(--accent)",
  border: "none",
} as const;
