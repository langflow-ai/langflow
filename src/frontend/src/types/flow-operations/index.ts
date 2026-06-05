import type { AllNodeType, EdgeType } from "@/types/flow";

export type AddNodesOp = {
  type: "add_nodes";
  nodes: AllNodeType[];
};

export type NodeFieldPathSegment = string | number;
export type NodeFieldPath = NodeFieldPathSegment[];

export type SetNodeFieldUpdate = {
  id: string;
  op: "set_field";
  path: NodeFieldPath;
  value: unknown;
};

export type DeleteNodeFieldUpdate = {
  id: string;
  op: "delete_field";
  path: NodeFieldPath;
};

export type OverwriteNodeUpdate = {
  id: string;
  op: "overwrite_node";
  node: AllNodeType;
};

export type UpdateNodeEntry =
  | SetNodeFieldUpdate
  | DeleteNodeFieldUpdate
  | OverwriteNodeUpdate;

export type UpdateNodesOp = {
  type: "update_nodes";
  updates: UpdateNodeEntry[];
};

export type DeleteNodesOp = {
  type: "delete_nodes";
  ids: string[];
};

export type AddEdgesOp = {
  type: "add_edges";
  edges: EdgeType[];
};

export type DeleteEdgesOp = {
  type: "delete_edges";
  ids: string[];
};

export type UpdateMetadataOp = {
  type: "update_metadata";
  fields: Record<string, unknown>;
  delete_keys?: string[];
};

export type FlowOperation =
  | AddNodesOp
  | UpdateNodesOp
  | DeleteNodesOp
  | AddEdgesOp
  | DeleteEdgesOp
  | UpdateMetadataOp;

export type FlowMutationOptions = {
  skipCollaborationEmit?: boolean;
  collaborationUpdates?: UpdateNodeEntry[];
};

export type CollaborationHistoryEntry = {
  forwardOps: FlowOperation[];
  inverseOps: FlowOperation[];
};

export type FlowOperationEmitOptions = {
  historyEntry?: CollaborationHistoryEntry;
};

export type FlowOperationSubmitPayload = {
  request_id: string;
  base_revision: number;
  operations: FlowOperation[];
};

export type FlowOperationAcceptedPayload = {
  request_id?: string | null;
  flow_id: string;
  revision: number;
  actor_user_id: string;
  forward_ops: FlowOperation[];
  created_at: string;
};
