import type { AllNodeType, EdgeType } from "@/types/flow";

/** Who performed an accepted operation batch (server-derived on accept). */
export type FlowOperationActorDelegate = "self" | "agent";

export type AddNodesOp = {
  type: "add_nodes";
  nodes: AllNodeType[];
};

export type UpdateNodesOp = {
  type: "update_nodes";
  nodes: AllNodeType[];
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
  actor_delegate: FlowOperationActorDelegate;
  forward_ops: FlowOperation[];
  created_at: string;
};
