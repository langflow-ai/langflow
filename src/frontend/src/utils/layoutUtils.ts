import { getRightHandleId } from "@/CustomNodes/utils/get-handle-id";
import { NodeType } from "@/types/flow";
import ELK from "elkjs/lib/elk.bundled.js";
import { Edge } from "reactflow";

const layoutOptions = {
  "elk.algorithm": "layered",
  "elk.direction": "RIGHT",
  "elk.layered.spacing.edgeNodeBetweenLayers": "40",
  "elk.spacing.nodeNode": "40",
  "elk.layered.nodePlacement.strategy": "SIMPLE",
};
const elk = new ELK();

// uses elkjs to give each node a layouted position
export const getLayoutedNodes = async (nodes: NodeType[], edges: Edge[]) => {
  const graph = {
    id: "root",
    layoutOptions,
    children: nodes.map((n) => {
      const targetPorts = Object.entries(n.data.node?.template ?? {}).map(
        ([_type, inputField], index) => ({
          id: getRightHandleId({
            inputTypes: inputField.input_types,
            type: inputField.type,
            fieldName: _type,
            id: n.id,
            proxy: inputField.proxy,
          }),

          // ⚠️ it's important to let elk know on which side the port is
          // in this example targets are on the left (WEST) and sources on the right (EAST)
          properties: {
            side: "WEST",
          },
        }),
      );

      const sourcePorts = Object.entries(n.data.node?.template ?? {}).map(
        ([_type, inputField], index) => ({
          id: getRightHandleId({
            inputTypes: inputField.input_types,
            type: inputField.type,
            fieldName: _type,
            id: n.id,
            proxy: inputField.proxy,
          }),
          properties: {
            side: "EAST",
          },
        }),
      );
      const width = 384;
      return {
        id: n.id,
        width: width,
        height: width * 3,
        // ⚠️ we need to tell elk that the ports are fixed, in order to reduce edge crossings
        properties: {
          "org.eclipse.elk.portConstraints": "FIXED_ORDER",
        },
        // we are also passing the id, so we can also handle edges without a sourceHandle or targetHandle option
        ports: [{ id: n.id }, ...targetPorts, ...sourcePorts],
      };
    }),
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
