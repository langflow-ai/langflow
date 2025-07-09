import { NODE_HEIGHT, NODE_WIDTH } from "@/constants/constants";
import { AllNodeType, EdgeType } from "@/types/flow";
import ELK, { ElkNode } from "elkjs/lib/elk.bundled.js";
import { cloneDeep } from "lodash";

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

// Improved layout options for manual auto-layout with better aesthetics and compact spacing
const improvedLayoutOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.components.direction": "DOWN",
  "elk.layered.spacing.edgeNodeBetweenLayers": "50", // Compact horizontal spacing
  "elk.spacing.nodeNode": "30", // Tighter vertical spacing between nodes
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  "elk.separateConnectedComponents": "true",
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  "elk.spacing.componentComponent": "80", // Moderate spacing between disconnected components
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
  "elk.layered.spacing.componentComponentSpacing": "60", // Reduced component separation
  "elk.layered.thoroughness": "10", // Higher quality layout
  "elk.layered.priority.direction": "10", // Prioritize flow direction
  "elk.layered.priority.shortness": "8", // Prefer much shorter edges
  "elk.partitioning.activate": "true", // Better partitioning
  "elk.stress.desiredEdgeLength": "60", // Shorter preferred edge length
  "elk.layered.compaction.connectedComponents": "true", // Compact connected components
  "elk.layered.compaction.postCompaction.strategy": "EDGE_LENGTH", // Post-compaction for tighter layout
};
const elk = new ELK();

// uses elkjs to give each node a layouted position
export const getLayoutedNodes = async (
  nodes: AllNodeType[],
  edges: EdgeType[],
): Promise<AllNodeType[]> => {
  const graph = {
    id: "root",
    layoutOptions,
    children: cloneDeep(nodes).map((n) => {
      const targetPorts = edges
        .filter((e) => e.source === n.id)
        .map((e) => ({
          id: e.sourceHandle,
          properties: {
            side: "EAST",
          },
        }));

      const sourcePorts = edges
        .filter((e) => e.target === n.id)
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
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.sourceHandle || e.source],
      targets: [e.targetHandle || e.target],
    })),
  };
  const layoutedGraph = await elk.layout(graph);

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

// Improved layout function with better aesthetics for manual auto-layout
export const getImprovedLayoutedNodes = async (
  nodes: AllNodeType[],
  edges: EdgeType[],
): Promise<AllNodeType[]> => {
  const graph = {
    id: "root",
    layoutOptions: improvedLayoutOptions,
    children: cloneDeep(nodes).map((n) => {
      const targetPorts = edges
        .filter((e) => e.source === n.id)
        .map((e) => ({
          id: e.sourceHandle,
          properties: {
            side: "EAST",
          },
        }));

      const sourcePorts = edges
        .filter((e) => e.target === n.id)
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
        properties: {
          "org.eclipse.elk.portConstraints": "FIXED_ORDER",
        },
        ports: [{ id: n.id }, ...targetPorts, ...sourcePorts],
      };
    }) as ElkNode[],
    edges: edges.map((e) => ({
      id: e.id,
      sources: [e.sourceHandle || e.source],
      targets: [e.targetHandle || e.target],
    })),
  };
  
  const layoutedGraph = await elk.layout(graph);

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
