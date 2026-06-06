// Presentational sequence-diagram canvas. Given the contract's `nodes`/`edges`
// it renders a real @xyflow/react canvas with the custom actor/system node
// types, pan/zoom controls, a minimap, a dotted background, and the edge legend
// — all themed off the lothal surface tokens. Pure render: it takes the diagram
// as props (the data-fetching lives in <CanvasSurface>), so the gallery can drop
// it in with a seeded payload to verify rendering without a backend.

import {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  ReactFlow,
} from "@xyflow/react";
import { useMemo } from "react";
import type {
  DiagramEdge,
  DiagramNode,
} from "@/controllers/API/queries/lothal";
import { ActorNode } from "./ActorNode";
import { CanvasLegend } from "./CanvasLegend";
import { toFlowEdges, toFlowNodes } from "./canvasGraph";
import { SystemNode } from "./SystemNode";

// Registered once at module scope — xyflow warns if nodeTypes is a new object
// on every render.
const nodeTypes = { actorNode: ActorNode, systemNode: SystemNode };

export function DiagramCanvas({
  nodes,
  edges,
}: {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
}) {
  const flowNodes = useMemo(() => toFlowNodes(nodes), [nodes]);
  const flowEdges = useMemo(() => toFlowEdges(edges), [edges]);

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.25 }}
        minZoom={0.2}
        nodesConnectable={false}
        deleteKeyCode={null}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={20}
          size={1}
          color="var(--border-strong)"
        />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor="var(--accent)"
          nodeStrokeColor="var(--border-strong)"
          maskColor="var(--minimap-mask)"
          style={{
            background: "var(--surface)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
          }}
        />
        <Panel position="top-right">
          <CanvasLegend />
        </Panel>
      </ReactFlow>
    </div>
  );
}
