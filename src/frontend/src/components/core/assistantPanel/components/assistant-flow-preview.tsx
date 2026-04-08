import {
  Background,
  type Edge,
  type Node,
  ReactFlow,
  ReactFlowProvider,
} from "@xyflow/react";
import { Check, GitBranch } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import useFlowStore from "@/stores/flowStore";

const APPROVED_DISPLAY_DURATION_MS = 3000;

interface FlowPreviewData {
  flow: Record<string, unknown>;
  name: string;
  nodeCount: number;
  edgeCount: number;
  graph: string;
}

interface AssistantFlowPreviewProps {
  flowPreview: FlowPreviewData;
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
}: AssistantFlowPreviewProps) {
  const [showApproved, setShowApproved] = useState(false);
  const paste = useFlowStore((state) => state.paste);

  const { nodes, edges } = useMemo(
    () => extractReactFlowData(flowPreview.flow),
    [flowPreview.flow],
  );

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
    <div className="max-w-[80%] rounded-lg border border-border bg-muted/30 p-4">
      {/* Flow header */}
      <div className="mb-3 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-[10px] bg-[#8B5CF6]">
          <GitBranch className="h-4 w-4 text-white" />
        </div>
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

      {/* Mini flow canvas */}
      {nodes.length > 0 && (
        <div className="mb-4 h-[120px] w-full overflow-hidden rounded-md border border-border bg-background">
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
              <Background gap={12} size={0.5} />
            </ReactFlow>
          </ReactFlowProvider>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2">
        {showApproved ? (
          <div className="flex h-8 items-center gap-1.5 text-sm font-medium text-accent-emerald-foreground">
            <Check className="h-4 w-4" />
            <span>Added to flow</span>
          </div>
        ) : (
          <button
            type="button"
            className="h-8 rounded-[10px] bg-white px-4 text-sm font-medium text-zinc-900 transition-colors hover:bg-zinc-100"
            onClick={handleAddToFlow}
          >
            Add to Flow
          </button>
        )}
      </div>
    </div>
  );
}
