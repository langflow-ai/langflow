import ForwardedIconComponent from "@/components/common/genericIconComponent";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { FlowHistoryEntryFull } from "@/types/flow/history";
import { Background, ReactFlow, ReactFlowProvider } from "@xyflow/react";
import { useCallback, useEffect, useMemo } from "react";

interface FlowHistoryPreviewProps {
  historyEntry: FlowHistoryEntryFull;
  onClose: () => void;
  onActivate: (historyId: string) => void;
  isActivating?: boolean;
}

function PreviewCanvas({
  historyEntry,
}: {
  historyEntry: FlowHistoryEntryFull;
}) {
  const { nodes, edges } = useMemo(() => {
    const data = historyEntry.data;
    if (!data) return { nodes: [], edges: [] };

    const rawNodes = (data.nodes || []).map((node: any) => ({
      id: node.id,
      type: "default",
      position: node.position || { x: 0, y: 0 },
      data: {
        label: node.data?.type || node.data?.node?.display_name || node.id,
      },
      style: {
        borderRadius: "8px",
        padding: "10px",
        fontSize: "12px",
        minWidth: "150px",
      },
      className: "bg-background border border-border",
    }));

    const rawEdges = (data.edges || []).map((edge: any) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
      type: "default",
    }));

    return { nodes: rawNodes, edges: rawEdges };
  }, [historyEntry.data]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      elementsSelectable={false}
      panOnDrag={true}
      zoomOnScroll={true}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      proOptions={{ hideAttribution: true }}
    >
      <Background />
    </ReactFlow>
  );
}

export default function FlowHistoryPreview({
  historyEntry,
  onClose,
  onActivate,
  isActivating,
}: FlowHistoryPreviewProps) {
  const handleActivate = useCallback(() => {
    onActivate(historyEntry.id);
  }, [historyEntry.id, onActivate]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const nodeCount = historyEntry.data?.nodes?.length ?? 0;
  const edgeCount = historyEntry.data?.edges?.length ?? 0;

  return (
    <div className="fixed inset-0 z-[60] flex flex-col bg-background">
      {/* Banner */}
      <div className="flex items-center justify-between border-b bg-muted/50 px-4 py-2">
        <div className="flex items-center gap-3">
          <ForwardedIconComponent name="Eye" className="h-4 w-4" />
          <span className="text-sm font-medium">
            Previewing {historyEntry.version_tag}
          </span>
          {historyEntry.description && (
            <span className="text-xs text-muted-foreground">
              — {historyEntry.description}
            </span>
          )}
          <Badge variant="secondaryStatic" size="sm">
            Read-only
          </Badge>
          <span className="text-xs text-muted-foreground">
            {nodeCount} nodes, {edgeCount} edges
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={handleActivate}
            loading={isActivating}
          >
            <ForwardedIconComponent
              name="RotateCcw"
              className="mr-1 h-3 w-3"
            />
            Activate This Version
          </Button>
          <Button variant="outline" size="sm" onClick={onClose}>
            <ForwardedIconComponent name="X" className="mr-1 h-3 w-3" />
            Exit Preview
          </Button>
        </div>
      </div>

      {/* Canvas */}
      <div className="flex-1">
        <ReactFlowProvider>
          <PreviewCanvas historyEntry={historyEntry} />
        </ReactFlowProvider>
      </div>
    </div>
  );
}
