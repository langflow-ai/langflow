import { Edge } from "@xyflow/react";
import { AllNodeType, EdgeType, FlowType } from "../flow";

export type addEscapedHandleIdsToEdgesType = {
  edges: EdgeType[];
};

export type updateEdgesHandleIdsType = {
  nodes: AllNodeType[];
  edges: EdgeType[];
};

export type generateFlowType = { newFlow: FlowType; removedEdges: Edge[] };

export type findLastNodeType = {
  nodes: AllNodeType[];
  edges: EdgeType[];
};
