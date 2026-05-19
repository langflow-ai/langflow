import {
  Background,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import { ArrowRight, Check, GitBranch, X } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import useFlowStore from "@/stores/flowStore";
import type { FlowProposalStatus } from "../assistant-panel.types";
import {
  GHOST_PRIMARY_BUTTON,
  GHOST_SECONDARY_BUTTON,
} from "../helpers/button-styles";

const APPROVED_DISPLAY_DURATION_MS = 3000;

/**
 * Above this many components the thumbnail is an unreadable tangle, so the
 * mini-canvas is skipped and a short notice is shown instead. The flow can
 * still be added/replaced — only the visual preview is suppressed.
 */
const MAX_PREVIEW_NODES = 7;

interface FlowPreviewData {
  flow: Record<string, unknown>;
  name: string;
  nodeCount: number;
  edgeCount: number;
  graph: string;
}

interface AssistantFlowPreviewProps {
  flowPreview: FlowPreviewData;
  /**
   * When provided, switches the card into gated mode:
   *  - "pending"   → Continue + Dismiss buttons, canvas untouched
   *  - "applied"   → muted preview with "Added to canvas" label
   *  - "dismissed" → muted preview with "Dismissed" label
   *
   * When omitted, falls back to the legacy "Add to Flow" path which
   * pastes the flow into the existing canvas via `paste()`.
   */
  status?: FlowProposalStatus;
  /**
   * Apply handler. Receives a ``mode`` so the card can distinguish
   * additive vs destructive intent. Callers from older code paths that
   * still invoke ``onApply()`` (zero args) default to ``"replace"`` for
   * backwards compatibility with the original single-button design.
   */
  onApply?: (mode: "replace" | "add") => void;
  onDismiss?: () => void;
}

const defaultNodeStyle = {
  fontSize: "11px",
  fontWeight: 500,
  padding: "4px 10px",
  borderRadius: "8px",
  border: "1px solid var(--border)",
  background: "var(--background)",
  color: "var(--foreground)",
};

/** Extract ReactFlow-compatible nodes and edges from the flow data */
function extractReactFlowData(flow: Record<string, unknown>): {
  nodes: Node[];
  edges: Edge[];
} {
  const data = flow.data as
    | {
        nodes?: {
          id?: string;
          position?: { x: number; y: number };
          data?: { type?: string; id?: string };
        }[];
        edges?: {
          id?: string;
          source?: string;
          target?: string;
        }[];
      }
    | undefined;

  if (!data?.nodes) return { nodes: [], edges: [] };

  // Scale down positions to fit the mini canvas
  const positions = data.nodes.map((n) => n.position ?? { x: 0, y: 0 });
  const maxX = Math.max(...positions.map((p) => p.x), 1);
  const scale = 250 / maxX;

  const nodes: Node[] = data.nodes.map((n, i) => ({
    id: n.id || `node-${i}`,
    type: "default",
    position: {
      x: (n.position?.x ?? 0) * scale + 20,
      y: (n.position?.y ?? 0) * scale + 30,
    },
    data: { label: n.data?.type || "Unknown" },
    style: defaultNodeStyle,
    draggable: false,
    selectable: false,
  }));

  const edges: Edge[] = (data.edges ?? []).map((e, i) => ({
    id: e.id || `edge-${i}`,
    source: e.source || "",
    target: e.target || "",
    animated: true,
    style: { stroke: "var(--muted-foreground)", strokeWidth: 1.5 },
  }));

  return { nodes, edges };
}

export function AssistantFlowPreview({
  flowPreview,
  status,
  onApply,
  onDismiss,
}: AssistantFlowPreviewProps) {
  const [showApproved, setShowApproved] = useState(false);
  const paste = useFlowStore((state) => state.paste);

  const { nodes, edges } = useMemo(
    () => extractReactFlowData(flowPreview.flow),
    [flowPreview.flow],
  );

  // The reported node count is authoritative; fall back to the parsed nodes.
  const nodeCount = flowPreview.nodeCount || nodes.length;
  const previewDisabled = nodeCount > MAX_PREVIEW_NODES;

  const handleAddToFlow = useCallback(() => {
    const data = flowPreview.flow.data as
      | {
          nodes?: Record<string, unknown>[];
          edges?: Record<string, unknown>[];
        }
      | undefined;
    if (!data?.nodes) return;

    paste(
      { nodes: data.nodes as never[], edges: (data.edges ?? []) as never[] },
      { x: 100, y: 100 },
    );
    setShowApproved(true);
    setTimeout(() => setShowApproved(false), APPROVED_DISPLAY_DURATION_MS);
  }, [flowPreview.flow, paste]);

  return (
    <div className="max-w-[80%] py-1">
      {/* Flow header */}
      <div className="mb-2 flex items-center gap-2">
        <GitBranch className="h-4 w-4 text-foreground/80" />
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-foreground">
            {flowPreview.name || "Untitled Flow"}
          </span>
          <span className="text-xs text-muted-foreground">
            {flowPreview.nodeCount} components, {flowPreview.edgeCount}{" "}
            connections
          </span>
        </div>
      </div>

      {/* Preview is skipped for large graphs — a thumbnail of that many
          nodes is an unreadable tangle. The flow can still be added. */}
      {previewDisabled && (
        <div className="mb-3 w-fit rounded-md border border-dashed border-border bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground">
          Preview disabled — too many components ({nodeCount}).
        </div>
      )}

      {/* Mini flow canvas */}
      {!previewDisabled && nodes.length > 0 && (
        <div className="mb-3 h-[120px] w-full overflow-hidden rounded-md bg-muted/30">
          <ReactFlowProvider>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              fitView
              fitViewOptions={{ padding: 0.3 }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
              panOnDrag={false}
              zoomOnScroll={false}
              zoomOnPinch={false}
              zoomOnDoubleClick={false}
              preventScrolling={false}
              proOptions={{ hideAttribution: true }}
            >
              <Background id="assistant-preview-bg" gap={12} size={0.5} />
            </ReactFlow>
          </ReactFlowProvider>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1">{renderActions()}</div>
    </div>
  );

  function renderActions() {
    if (status === "pending") {
      return (
        <>
          {/* Primary action: ADD to canvas. Non-destructive, keeps existing
              nodes/edges intact. Keeps the legacy `assistant-flow-continue-button`
              alias so older E2E specs still find it. */}
          <button
            type="button"
            data-testid="assistant-flow-add-button"
            data-add-button-alias="assistant-flow-continue-button"
            className={GHOST_PRIMARY_BUTTON}
            onClick={() => onApply?.("add")}
          >
            <span>Add to canvas</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </button>
          {/* Secondary action: REPLACE canvas. Destructive — same muted ghost
              styling as Dismiss; tooltip carries the destructive intent. */}
          <button
            type="button"
            data-testid="assistant-flow-replace-button"
            className={GHOST_SECONDARY_BUTTON}
            onClick={() => onApply?.("replace")}
            title="Discard the current canvas and replace it with this flow"
          >
            <span>Replace canvas</span>
          </button>
          <button
            type="button"
            data-testid="assistant-flow-dismiss-button"
            className={GHOST_SECONDARY_BUTTON}
            onClick={() => onDismiss?.()}
          >
            <X className="h-3.5 w-3.5" />
            <span>Dismiss</span>
          </button>
        </>
      );
    }
    if (status === "applied") {
      return (
        <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-accent-emerald-foreground">
          <Check className="h-3.5 w-3.5" />
          <span>Added to canvas</span>
        </div>
      );
    }
    if (status === "dismissed") {
      return (
        <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-muted-foreground line-through">
          <span>Dismissed</span>
        </div>
      );
    }
    // Legacy "Add to Flow" path — no status prop provided
    if (showApproved) {
      return (
        <div className="flex h-7 items-center gap-1.5 px-2 text-sm font-medium text-accent-emerald-foreground">
          <Check className="h-3.5 w-3.5" />
          <span>Added to flow</span>
        </div>
      );
    }
    return (
      <button
        type="button"
        className={GHOST_PRIMARY_BUTTON}
        onClick={handleAddToFlow}
      >
        <span>Add to Flow</span>
        <ArrowRight className="h-3.5 w-3.5" />
      </button>
    );
  }
}
