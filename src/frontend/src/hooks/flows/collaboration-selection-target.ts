import type { OnSelectionChangeParams } from "@xyflow/react";

import type { CollaborationSelectionTarget } from "@/types/flow-collaboration";

/** Map React Flow selection to a single graph target for V1 collaboration selection sync. */
export function selectionTargetFromFlowSelection(
  selection: OnSelectionChangeParams | null,
): CollaborationSelectionTarget | null {
  if (!selection) {
    return null;
  }

  const nodeCount = selection.nodes?.length ?? 0;
  const edgeCount = selection.edges?.length ?? 0;

  if (nodeCount === 1 && edgeCount === 0) {
    return { kind: "node", id: selection.nodes[0].id };
  }

  if (edgeCount === 1 && nodeCount === 0) {
    return { kind: "edge", id: selection.edges[0].id };
  }

  return null;
}

export function serializeCollaborationSelectionTarget(
  target: CollaborationSelectionTarget | null,
): string {
  if (!target) {
    return "";
  }
  return `${target.kind}:${target.id}`;
}
