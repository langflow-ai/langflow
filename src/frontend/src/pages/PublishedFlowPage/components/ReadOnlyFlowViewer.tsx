import { Background, ReactFlow, ReactFlowProvider, type Viewport } from "@xyflow/react";
import { useEffect } from "react";
import GenericNode from "@/CustomNodes/GenericNode";
import NoteNode from "@/CustomNodes/NoteNode";
import { DefaultEdge } from "@/CustomEdges";
import useFlowStore from "@/stores/flowStore";
import type { AllNodeType, EdgeType } from "@/types/flow";

interface ReadOnlyFlowViewerProps {
  nodes: AllNodeType[];
  edges: EdgeType[];
  viewport?: Viewport;
}

const nodeTypes = {
  genericNode: GenericNode,
  noteNode: NoteNode,
};

const edgeTypes = {
  default: DefaultEdge,
};

export default function ReadOnlyFlowViewer({
  nodes,
  edges,
  viewport,
}: ReadOnlyFlowViewerProps): JSX.Element {
  // Populate FlowStore for GenericNode components to read
  useEffect(() => {
    console.log("[ReadOnlyFlowViewer] MOUNT - Received nodes from props:", nodes.length);
    console.log("[ReadOnlyFlowViewer] MOUNT - Nodes data:", JSON.stringify(nodes.map(n => ({ id: n.id, type: n.type }))));

    const flowStore = useFlowStore.getState();

    // Log what's currently in FlowStore BEFORE we change it
    console.log("[ReadOnlyFlowViewer] BEFORE - FlowStore has:", flowStore.nodes.length, "nodes");
    console.log("[ReadOnlyFlowViewer] BEFORE - FlowStore nodes:", JSON.stringify(flowStore.nodes.map(n => ({ id: n.id, type: n.type }))));

    // Set nodes/edges for GenericNode components to read
    flowStore.setNodes(nodes);
    flowStore.setEdges(edges);

    console.log("[ReadOnlyFlowViewer] AFTER - Set FlowStore to published snapshot:", nodes.length, "nodes");

    return () => {
      console.log("[ReadOnlyFlowViewer] UNMOUNT - Cleanup");
    };
  }, [nodes, edges]);

  const MIN_ZOOM = 0.25;
  const MAX_ZOOM = 2;

  return (
    <div className="h-full w-full bg-canvas">
      <ReactFlowProvider>
        <ReactFlow<AllNodeType, EdgeType>
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          // Read-only mode - disable all interactions
          nodesDraggable={false}
          nodesConnectable={false}
          nodesFocusable={false}
          edgesFocusable={false}
          elementsSelectable={false}
          zoomOnScroll={true}
          zoomOnPinch={true}
          panOnDrag={true}
          panOnScroll={false}
          // Fit to view on initial load
          fitView={true}
          fitViewOptions={{
            minZoom: MIN_ZOOM,
            maxZoom: MAX_ZOOM,
          }}
          defaultViewport={viewport ?? { x: 0, y: 0, zoom: 1 }}
          minZoom={MIN_ZOOM}
          maxZoom={MAX_ZOOM}
          proOptions={{ hideAttribution: true }}
          // Disable all callbacks - this is read-only
          onNodesChange={undefined}
          onEdgesChange={undefined}
          onConnect={undefined}
          deleteKeyCode={[]}
          className="theme-attribution"
          tabIndex={-1}
        >
          <Background size={2} gap={20} className="" />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}
