// Pure mapping from the `/diagram` contract shape to xyflow render props.
//
// Kept free of any runtime @xyflow/react import (types only, erased at build)
// so it's trivially unit-testable: counts, kind defaults, and edge styling are
// all deterministic. The presentational <DiagramCanvas> feeds the output of
// these functions straight into <ReactFlow>.
//
// Edge kinds are a render hint the model emits alongside the canonical graph:
// `sync` (solid call), `async` (dashed, in-flight), `return` (dashed reply).
// When `data.kind` is absent we fall back to the top-level `animated` flag. The
// backend sets `animated` for any dashed message — async OR return — so it can't
// tell the two apart; we therefore default an animated-but-kindless edge to the
// conservative `return` style (muted, static) rather than `async`'s accent +
// animation, which would over-claim an in-flight call. Node kinds default from
// the node type (actor→person, system→service).

import type {
  Edge as FlowEdge,
  Node as FlowNode,
  MarkerType,
} from "@xyflow/react";
import type {
  DiagramEdge,
  DiagramGraph,
  DiagramNode,
  EdgeKind,
  NodeKind,
} from "@/controllers/API/queries/lothal";

const ARROW_CLOSED = "arrowclosed" as MarkerType;

/** Default node `kind` from its type when the converter didn't supply one. */
export function defaultNodeKind(type: DiagramNode["type"]): NodeKind {
  return type === "actorNode" ? "person" : "service";
}

/** Visual treatment for each edge kind. Lives here so it's covered by tests. */
export function edgeStyle(kind: EdgeKind): {
  animated: boolean;
  stroke: string;
  strokeDasharray?: string;
} {
  switch (kind) {
    case "async":
      // In-flight message — dashed and animated, drawn in the accent.
      return {
        animated: true,
        stroke: "var(--accent)",
        strokeDasharray: "6 5",
      };
    case "return":
      // A reply — dashed and muted, visually secondary to the call.
      return {
        animated: false,
        stroke: "var(--ink-soft)",
        strokeDasharray: "4 4",
      };
    default:
      // sync — a solid call line in the accent.
      return { animated: false, stroke: "var(--accent)" };
  }
}

/**
 * The edge kind: the explicit `data.kind` hint when present, else inferred from
 * the top-level `animated` flag. `animated` marks a dashed message but can't
 * distinguish async from return, so a kindless animated edge falls back to the
 * conservative `return` style rather than `async` (which would add a spurious
 * accent + animation); a non-animated kindless edge defaults to `sync`.
 */
export function resolveEdgeKind(edge: DiagramEdge): EdgeKind {
  return edge.data?.kind ?? (edge.animated ? "return" : "sync");
}

function toFlowNode(node: DiagramNode): FlowNode {
  return {
    id: node.id,
    type: node.type,
    position: node.position,
    data: {
      ...node.data,
      kind: node.data.kind ?? defaultNodeKind(node.type),
    },
  };
}

function toFlowEdge(edge: DiagramEdge): FlowEdge {
  const kind = resolveEdgeKind(edge);
  const { animated, stroke, strokeDasharray } = edgeStyle(kind);
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.data?.label,
    animated,
    data: { ...edge.data, kind },
    markerEnd: { type: ARROW_CLOSED, color: stroke },
    style: { stroke, strokeWidth: 1.6, strokeDasharray },
    labelBgPadding: [6, 3],
    labelBgBorderRadius: 6,
  };
}

/** Map the contract diagram to xyflow nodes, ordered as received. */
export function toFlowNodes(nodes: DiagramNode[]): FlowNode[] {
  return nodes.map(toFlowNode);
}

/**
 * Map the contract diagram to xyflow edges, sorted by `data.order` so the
 * sequence reads top-to-bottom regardless of payload order.
 */
export function toFlowEdges(edges: DiagramEdge[]): FlowEdge[] {
  return [...edges]
    .sort((a, b) => (a.data?.order ?? 0) - (b.data?.order ?? 0))
    .map(toFlowEdge);
}

/** True when the diagram has no nodes to render (not generated yet). */
export function isEmptyDiagram(diagram: DiagramGraph | undefined): boolean {
  return !diagram || diagram.nodes.length === 0;
}
