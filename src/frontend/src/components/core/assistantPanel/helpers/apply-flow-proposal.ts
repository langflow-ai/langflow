/**
 * Apply a gated flow proposal onto the live canvas — the shared body behind the
 * "Add to canvas" (merge) and "Replace canvas" (overwrite) actions. Extracted
 * from the chat hook to keep it within the file-size budget and to isolate the
 * canvas-mutation concern from the message/state bookkeeping.
 */

import type { useUpdateNodeInternals } from "@xyflow/react";
import useFlowStore from "@/stores/flowStore";
import type { PendingFlowProposal } from "../assistant-panel.types";
import { applyFlowUpdate, notifyNodesUntilMounted } from "./apply-flow-update";
import { mergeFlowIntoCanvas } from "./merge-flow-into-canvas";

type UpdateNodeInternals = ReturnType<typeof useUpdateNodeInternals>;

interface PositionedNode {
  id: string;
  position: { x: number; y: number };
}
interface SimpleEdge {
  id: string;
  source: string;
  target: string;
}

export function applyFlowProposalToCanvas(
  proposal: PendingFlowProposal,
  mode: "replace" | "add",
  updateNodeInternals: UpdateNodeInternals,
): void {
  if (mode === "add") {
    // Additive merge: ids remapped on collision, edges rewritten, positions
    // offset right of the existing bounding box (no overlap).
    const store = useFlowStore.getState();
    const flow = proposal.flow as {
      data?: { nodes?: unknown[]; edges?: unknown[] };
    };
    const proposalNodes = (flow.data?.nodes as PositionedNode[]) ?? [];
    const proposalEdges = (flow.data?.edges as SimpleEdge[]) ?? [];
    const existingIds = new Set(
      (store.nodes as PositionedNode[]).map((n) => n.id),
    );
    const merged = mergeFlowIntoCanvas(
      store.nodes as PositionedNode[],
      store.edges as SimpleEdge[],
      { nodes: proposalNodes, edges: proposalEdges },
    );
    // Atomic nodes+edges in one render so edges to loop/dynamic handles draw
    // without a refresh (a split setNodes+setEdges draws them a frame late).
    store.setNodesAndEdges(merged.nodes as never[], merged.edges as never[]);
    const addedIds = merged.nodes
      .map((n) => n.id)
      .filter((id) => !existingIds.has(id));
    notifyNodesUntilMounted(addedIds, updateNodeInternals);
  } else {
    applyFlowUpdate(
      { event: "flow_update", action: "set_flow", flow: proposal.flow },
      updateNodeInternals,
    );
  }
  for (const tail of proposal.tailUpdates ?? []) {
    applyFlowUpdate(tail, updateNodeInternals);
  }
}
