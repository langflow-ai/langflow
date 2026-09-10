import ELK, { type ElkNode } from "elkjs/lib/elk.bundled.js";
import { cloneDeep } from "lodash";
import { NODE_HEIGHT, NODE_WIDTH } from "@/constants/constants";
import type { AllNodeType, EdgeType } from "@/types/flow";

const layoutOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.components.direction": "DOWN",
  "elk.layered.spacing.edgeNodeBetweenLayers": "40",
  "elk.spacing.nodeNode": "40",
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.separateConnectedComponents": "true",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.spacing.componentComponent": `${NODE_WIDTH}`,
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
};
const elk = new ELK();

// Deterministic grid used when ELK cannot lay the graph out. Guarantees every
// node still receives a numeric position so React Flow never adopts a node
// whose `position` is undefined.
export const getFallbackGridPositions = (
  nodes: AllNodeType[],
): AllNodeType[] => {
  const columns = Math.max(1, Math.ceil(Math.sqrt(nodes.length)));
  return nodes.map((node, index) => ({
    ...node,
    position: {
      x: (index % columns) * (NODE_WIDTH + 80),
      y: Math.floor(index / columns) * (NODE_HEIGHT / 2 + 80),
    },
  }));
};

// uses elkjs to give each node a layouted position
export const getLayoutedNodes = async (
  nodes: AllNodeType[],
  edges: EdgeType[],
): Promise<AllNodeType[]> => {
  const graph = {
    id: "root",
    layoutOptions,
    children: cloneDeep(nodes).map((n) => {
      // ELK rejects any id that is not a string or integer, so ports derived
      // from an absent sourceHandle/targetHandle must be dropped rather than
      // emitted with `id: undefined`. Edges referencing those handles fall back
      // to the always-present node-id port below.
      const targetPorts = edges
        .filter((e) => e.source === n.id && e.sourceHandle)
        .map((e) => ({
          id: e.sourceHandle,
          properties: {
            side: "EAST",
          },
        }));

      const sourcePorts = edges
        .filter((e) => e.target === n.id && e.targetHandle)
        .map((e) => ({
          id: e.targetHandle,
          properties: {
            side: "WEST",
          },
        }));
      return {
        id: n.id,
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        // ⚠️ we need to tell elk that the ports are fixed, in order to reduce edge crossings
        properties: {
          "org.eclipse.elk.portConstraints": "FIXED_ORDER",
        },
        // we are also passing the id, so we can also handle edges without a sourceHandle or targetHandle option
        ports: [{ id: n.id }, ...targetPorts, ...sourcePorts],
      };
    }) as ElkNode[],
    edges: edges.map((e, index) => ({
      // Flows built programmatically (e.g. the /starter-projects/ payload) have
      // no edge id; ELK requires one.
      id: e.id ?? `elk-edge-${index}`,
      sources: [e.sourceHandle || e.source],
      targets: [e.targetHandle || e.target],
    })),
  };

  let layoutedGraph: ElkNode;
  try {
    layoutedGraph = await elk.layout(graph);
  } catch (error) {
    console.error(
      "getLayoutedNodes: ELK layout failed, using grid fallback",
      error,
    );
    return getFallbackGridPositions(nodes);
  }

  const layoutedNodes = nodes.map((node) => {
    const layoutedNode = layoutedGraph.children?.find(
      (lgNode) => lgNode.id === node.id,
    );

    return {
      ...node,
      position: {
        x: layoutedNode?.x ?? 0,
        y: layoutedNode?.y ?? 0,
      },
    };
  });
  return layoutedNodes;
};
