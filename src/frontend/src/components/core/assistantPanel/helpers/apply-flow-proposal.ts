/**
 * Apply a gated flow proposal onto the live canvas — the shared body behind the
 * "Add to canvas" (merge) and "Replace canvas" (overwrite) actions. Extracted
 * from the chat hook to keep it within the file-size budget and to isolate the
 * canvas-mutation concern from the message/state bookkeeping.
 */

import type { useUpdateNodeInternals } from "@xyflow/react";
import i18n from "@/i18n";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import {
  type ConstraintViolation,
  filterPlaceableSelection,
} from "@/utils/componentConstraints";
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

/**
 * The proposal card advertises the full node/edge counts, so a policy drop
 * must be surfaced — a silent drop leaves the canvas diverging from what the
 * user accepted (and can strand required inputs whose edge was pruned).
 */
function notifyPlacementViolations(violations: ConstraintViolation[]): void {
  if (violations.length === 0) return;
  const messages: string[] = [];
  if (violations.some((v) => v.reason === "singleton")) {
    messages.push(i18n.t("assistant.duplicateComponentsNotAdded"));
  }
  if (violations.some((v) => v.reason === "exclusivity")) {
    messages.push(i18n.t("assistant.exclusiveComponentsNotAdded"));
  }
  useAlertStore.getState().setNoticeData({ title: messages.join(" ") });
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
    // Writes the store directly (not via `paste`), so re-enforce placement policy.
    const placeable = filterPlaceableSelection(
      { nodes: proposalNodes as never[], edges: proposalEdges as never[] },
      store.nodes as Array<{ data?: { type?: string } }>,
    );
    notifyPlacementViolations(placeable.violations);
    const merged = mergeFlowIntoCanvas(
      store.nodes as PositionedNode[],
      store.edges as SimpleEdge[],
      { nodes: placeable.nodes, edges: placeable.edges },
    );
    // Atomic nodes+edges in one render so edges to loop/dynamic handles draw
    // without a refresh (a split setNodes+setEdges draws them a frame late).
    store.setNodesAndEdges(merged.nodes as never[], merged.edges as never[]);
    const addedIds = merged.nodes
      .map((n) => n.id)
      .filter((id) => !existingIds.has(id));
    notifyNodesUntilMounted(addedIds, updateNodeInternals);
  } else {
    // Replace targets an empty canvas, but the proposal can conflict with
    // itself (e.g. two ChatInputs); filter a copy so re-apply stays intact.
    const flow = proposal.flow as {
      data?: { nodes?: unknown[]; edges?: unknown[] };
    };
    const placeable = filterPlaceableSelection(
      {
        nodes: (flow.data?.nodes ?? []) as never[],
        edges: (flow.data?.edges ?? []) as never[],
      },
      [],
    );
    notifyPlacementViolations(placeable.violations);
    applyFlowUpdate(
      {
        event: "flow_update",
        action: "set_flow",
        flow: {
          ...proposal.flow,
          data: {
            ...flow.data,
            nodes: placeable.nodes,
            edges: placeable.edges,
          },
        },
      },
      updateNodeInternals,
    );
  }
  for (const tail of proposal.tailUpdates ?? []) {
    applyFlowUpdate(tail, updateNodeInternals);
  }
}
