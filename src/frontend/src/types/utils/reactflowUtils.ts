import { Edge } from "reactflow";
import { NodeType } from "../flow";

export type cleanEdgesType = {
  flow: {
    edges: Edge[];
    nodes: NodeType[];
  };
  updateEdge: (edge: Edge[]) => void;
};

export type updateEdgesHandleIdsType = {
  nodes: NodeType[];
  edges: Edge[];
  setEdges: (edges: Edge[]) => void;
};
