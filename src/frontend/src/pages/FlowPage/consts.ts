import { DefaultEdge } from "@/CustomEdges";
import GenericNode from "@/CustomNodes/GenericNode";
import NoteNode from "@/CustomNodes/NoteNode";

/**
 * Shared ReactFlow node/edge type registrations used by the main canvas
 * (PageComponent).
 */
export const nodeTypes = {
  genericNode: GenericNode,
  noteNode: NoteNode,
};

export const edgeTypes = {
  default: DefaultEdge,
};
