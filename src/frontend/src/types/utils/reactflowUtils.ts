import { Edge } from "reactflow";
import { FlowType, NodeType } from "../flow";

export type addEscapedHandleIdsToEdgesType = {
  edges: Edge[];
};

export type updateEdgesHandleIdsType = {
  nodes: NodeType[];
  edges: Edge[];
};

export type generateFlowType = { newFlow: FlowType; removedEdges: Edge[] };

export type findLastNodeType = {
  nodes: NodeType[];
  edges: Edge[];
};
