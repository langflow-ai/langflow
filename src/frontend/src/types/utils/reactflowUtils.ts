import { Edge } from "reactflow";
import { NodeType } from "../flow";

export type cleanEdgesType = {
  flow: {
    edges: Edge[];
    nodes: NodeType[];
  };
  updateEdge: (edge: Edge[]) => void;
};
