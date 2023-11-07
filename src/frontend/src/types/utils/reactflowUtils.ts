import { Edge, Node } from "reactflow";
import { NodeType } from "../flow";

export type cleanEdgesType = {
  flow: {
    edges: Edge[];
    nodes: NodeType[];
  };
  updateEdge: (edge: Edge[]) => void;
};

export type unselectAllNodesType = {
  updateNodes: (nodes: Node[]) => void;
  data: Node[] | null;
};
