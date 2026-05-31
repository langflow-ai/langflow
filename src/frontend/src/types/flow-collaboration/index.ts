import type {
  FlowOperation,
  FlowOperationAcceptedPayload,
  FlowOperationActorDelegate,
} from "@/types/flow-operations";

export type CollaborationPresenceUser = {
  user_id: string;
  username: string;
  profile_image?: string | null;
};

export type CollaborationSessionStartMessage = {
  type: "session.start";
};

export type CollaborationSessionReadyMessage = {
  type: "session.ready";
  connection_id: string;
  flow_id: string;
  current_revision: number;
  users: CollaborationPresenceUser[];
};

export type CollaborationSessionErrorMessage = {
  type: "session.error";
  code: string;
  detail: string;
};

export type CollaborationOperationSubmitMessage = {
  type: "operation.submit";
  request_id: string;
  base_revision: number;
  operations: FlowOperation[];
};

export type CollaborationOperationAcceptedMessage = {
  type: "operation.accepted";
} & FlowOperationAcceptedPayload;

export type CollaborationOperationRejectedMessage = {
  type: "operation.rejected";
  request_id?: string | null;
  status: number;
  detail: string;
  current_revision?: number | null;
};

export type CollaborationOperationBroadcastMessage = {
  type: "operation.broadcast";
  flow_id: string;
  revision: number;
  actor_user_id: string;
  actor_delegate: FlowOperationActorDelegate;
  forward_ops: FlowOperation[];
  created_at: string;
};

export type CollaborationPresenceUpdatedMessage = {
  type: "presence.updated";
  users: CollaborationPresenceUser[];
};

export type CollaborationMessageErrorMessage = {
  type: "message.error";
  detail: string;
};

export type CollaborationServerMessage =
  | CollaborationSessionReadyMessage
  | CollaborationSessionErrorMessage
  | CollaborationOperationAcceptedMessage
  | CollaborationOperationRejectedMessage
  | CollaborationOperationBroadcastMessage
  | CollaborationPresenceUpdatedMessage
  | CollaborationMessageErrorMessage;

export type CollaborationClientMessage =
  | CollaborationSessionStartMessage
  | CollaborationOperationSubmitMessage;

export type CollaborationConnectionStatus =
  | "idle"
  | "connecting"
  | "ready"
  | "disconnected"
  | "error";

export type CollaborationReloadReason =
  | "stale_revision"
  | "revision_gap"
  | "socket_closed"
  | "session_error";

export type CollaborationReloadDetail = {
  status?: number;
  detail?: string;
  currentRevision?: number | null;
  expectedRevision?: number | null;
  receivedRevision?: number | null;
};
