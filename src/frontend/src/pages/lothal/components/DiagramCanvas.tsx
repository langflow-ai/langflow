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
  ReactFlowProvider,
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

/** Presentational sequence-diagram canvas over the contract's nodes/edges. */
export function DiagramCanvas({
  nodes,
  edges,
  id,
  chrome = true,
  zoomOnScroll = true,
}: {
  nodes: DiagramNode[];
  edges: DiagramEdge[];
  /** Required to be unique when several canvases share a page (xyflow keys
   *  its internal store by flow id — colliding ids merge the flows). */
  id?: string;
  /** Hide controls/minimap/legend for embedded previews (e.g. the landing hero). */
  chrome?: boolean;
  /** Disable so an embedded canvas doesn't hijack page scrolling. */
  zoomOnScroll?: boolean;
}) {
  const flowNodes = useMemo(() => toFlowNodes(nodes), [nodes]);
  const flowEdges = useMemo(() => toFlowEdges(edges), [edges]);

  // Own provider: Langflow's ContextWrapper has an app-wide ReactFlowProvider,
  // and any flows sharing a store merge into one another (the landing renders
  // two canvases on one page). The nearest provider wins, isolating each.
  return (
    <ReactFlowProvider>
      <div style={{ height: "100%", width: "100%" }}>
        <ReactFlow
          id={id}
          nodes={flowNodes}
          edges={flowEdges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.25 }}
          minZoom={0.2}
          zoomOnScroll={zoomOnScroll}
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
          {chrome && <Controls showInteractive={false} />}
          {chrome && (
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
          )}
          {chrome && (
            <Panel position="top-right">
              <CanvasLegend />
            </Panel>
          )}
        </ReactFlow>
      </div>
    </ReactFlowProvider>
  );
}
