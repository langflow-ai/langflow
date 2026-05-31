import { useCallback, useEffect, useRef, useState } from "react";
import {
  applyPresenceJoined,
  applyPresenceLeft,
  applyPresenceSnapshot,
  applySelectionSnapshot,
  applySelectionUpdated,
} from "@/hooks/flows/flow-collaboration-state";
import { buildFlowCollaborationWebSocketUrl } from "@/hooks/flows/flow-collaboration-url";
import type {
  CollaborationConnectionStatus,
  CollaborationOperationAcceptedMessage,
  CollaborationOperationBroadcastMessage,
  CollaborationPresenceUser,
  CollaborationReloadDetail,
  CollaborationReloadReason,
  CollaborationSelectionTarget,
  CollaborationServerMessage,
  CollaborationSessionErrorMessage,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";
import type { FlowOperation } from "@/types/flow-operations";

type PendingOperationRequest = {
  resolve: (message: CollaborationOperationAcceptedMessage) => void;
  reject: (error: Error) => void;
};

export type UseFlowCollaborationOptions = {
  flowId: string | undefined;
  /** When false, the socket is closed and state is reset. Defaults to true when flowId is set. */
  enabled?: boolean;
  onRemoteOperation?: (message: CollaborationOperationBroadcastMessage) => void;
  onReloadRequired?: (
    reason: CollaborationReloadReason,
    detail?: CollaborationReloadDetail,
  ) => void;
  onSessionError?: (message: CollaborationSessionErrorMessage) => void;
};

export type UseFlowCollaborationReturn = {
  status: CollaborationConnectionStatus;
  connectionId: string | null;
  currentRevision: number | null;
  users: CollaborationPresenceUser[];
  selections: CollaborationUserSelection[];
  isReady: boolean;
  submitOperations: (
    operations: FlowOperation[],
    options?: { requestId?: string },
  ) => Promise<CollaborationOperationAcceptedMessage>;
  sendSelectionUpdate: (selected: CollaborationSelectionTarget | null) => void;
  disconnect: () => void;
};

function createRequestId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function parseServerMessage(data: string): CollaborationServerMessage | null {
  try {
    return JSON.parse(data) as CollaborationServerMessage;
  } catch {
    return null;
  }
}

export function useFlowCollaboration({
  flowId,
  enabled = true,
  onRemoteOperation,
  onReloadRequired,
  onSessionError,
}: UseFlowCollaborationOptions): UseFlowCollaborationReturn {
  const [status, setStatus] = useState<CollaborationConnectionStatus>("idle");
  const [connectionId, setConnectionId] = useState<string | null>(null);
  const [currentRevision, setCurrentRevision] = useState<number | null>(null);
  const [users, setUsers] = useState<CollaborationPresenceUser[]>([]);
  const [selections, setSelections] = useState<CollaborationUserSelection[]>(
    [],
  );

  const wsRef = useRef<WebSocket | null>(null);
  const mountedRef = useRef(true);
  const intentionalCloseRef = useRef(false);
  const currentRevisionRef = useRef<number | null>(null);
  const pendingRef = useRef<Map<string, PendingOperationRequest>>(new Map());

  const onRemoteOperationRef = useRef(onRemoteOperation);
  const onReloadRequiredRef = useRef(onReloadRequired);
  const onSessionErrorRef = useRef(onSessionError);

  onRemoteOperationRef.current = onRemoteOperation;
  onReloadRequiredRef.current = onReloadRequired;
  onSessionErrorRef.current = onSessionError;

  const setRevision = useCallback((revision: number) => {
    currentRevisionRef.current = revision;
    if (mountedRef.current) {
      setCurrentRevision(revision);
    }
  }, []);

  const rejectAllPending = useCallback((error: Error) => {
    for (const pending of pendingRef.current.values()) {
      pending.reject(error);
    }
    pendingRef.current.clear();
  }, []);

  const requestReload = useCallback(
    (reason: CollaborationReloadReason, detail?: CollaborationReloadDetail) => {
      onReloadRequiredRef.current?.(reason, detail);
    },
    [],
  );

  const handleRemoteBroadcast = useCallback(
    (message: CollaborationOperationBroadcastMessage) => {
      const expectedRevision = (currentRevisionRef.current ?? 0) + 1;
      if (message.revision !== expectedRevision) {
        requestReload("revision_gap", {
          expectedRevision,
          receivedRevision: message.revision,
          currentRevision: currentRevisionRef.current,
        });
        return;
      }

      setRevision(message.revision);
      onRemoteOperationRef.current?.(message);
    },
    [requestReload, setRevision],
  );

  const handleServerMessageRef = useRef<
    (message: CollaborationServerMessage) => void
  >(() => {});

  const handleServerMessage = useCallback(
    (message: CollaborationServerMessage) => {
      switch (message.type) {
        case "session.ready": {
          setConnectionId(message.connection_id);
          setRevision(message.current_revision);
          setStatus("ready");
          return;
        }
        case "session.error": {
          setStatus("error");
          onSessionErrorRef.current?.(message);
          requestReload("session_error", { detail: message.detail });
          return;
        }
        case "operation.accepted": {
          setRevision(message.revision);
          const requestId = message.request_id;
          if (requestId) {
            const pending = pendingRef.current.get(requestId);
            if (pending) {
              pendingRef.current.delete(requestId);
              pending.resolve(message);
              return;
            }
          }
          return;
        }
        case "operation.rejected": {
          const requestId = message.request_id;
          if (requestId) {
            const pending = pendingRef.current.get(requestId);
            if (pending) {
              pendingRef.current.delete(requestId);
              pending.reject(
                new Error(
                  message.detail || `Operation rejected (${message.status})`,
                ),
              );
            }
          }

          if (message.current_revision != null) {
            setRevision(message.current_revision);
          }

          if (message.status === 409) {
            requestReload("stale_revision", {
              status: message.status,
              detail: message.detail,
              currentRevision: message.current_revision,
            });
          }
          return;
        }
        case "operation.broadcast": {
          handleRemoteBroadcast(message);
          return;
        }
        case "presence.snapshot": {
          setUsers((currentUsers) =>
            applyPresenceSnapshot(currentUsers, message.users),
          );
          return;
        }
        case "presence.joined": {
          setUsers((currentUsers) =>
            applyPresenceJoined(currentUsers, message.user),
          );
          return;
        }
        case "presence.left": {
          setUsers((currentUsers) =>
            applyPresenceLeft(currentUsers, message.user_id),
          );
          setSelections((currentSelections) =>
            currentSelections.filter(
              (entry) => entry.user_id !== message.user_id,
            ),
          );
          return;
        }
        case "selection.snapshot": {
          setSelections((currentSelections) =>
            applySelectionSnapshot(currentSelections, message.selections),
          );
          return;
        }
        case "selection.updated": {
          setSelections((currentSelections) =>
            applySelectionUpdated(
              currentSelections,
              message.user_id,
              message.selected,
            ),
          );
          return;
        }
        default:
          return;
      }
    },
    [handleRemoteBroadcast, requestReload, setRevision],
  );

  handleServerMessageRef.current = handleServerMessage;

  const disconnect = useCallback(() => {
    intentionalCloseRef.current = true;
    rejectAllPending(new Error("Collaboration disconnected"));
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnectionId(null);
    currentRevisionRef.current = null;
    setCurrentRevision(null);
    setUsers([]);
    setSelections([]);
    setStatus("idle");
  }, [rejectAllPending]);

  const connect = useCallback(() => {
    if (!flowId || !enabled) {
      return;
    }

    intentionalCloseRef.current = false;
    rejectAllPending(new Error("Collaboration reconnecting"));
    setStatus("connecting");
    setConnectionId(null);
    currentRevisionRef.current = null;
    setCurrentRevision(null);
    setUsers([]);
    setSelections([]);

    const ws = new WebSocket(buildFlowCollaborationWebSocketUrl(flowId));
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }
      ws.send(JSON.stringify({ type: "session.start" }));
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }
      const message = parseServerMessage(String(event.data));
      if (!message) {
        return;
      }
      handleServerMessageRef.current(message);
    };

    ws.onerror = () => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }
      setStatus("error");
    };

    ws.onclose = () => {
      if (!mountedRef.current || wsRef.current !== ws) {
        return;
      }
      wsRef.current = null;
      rejectAllPending(new Error("Collaboration socket closed"));
      setStatus("disconnected");
      setConnectionId(null);

      if (!intentionalCloseRef.current) {
        requestReload("socket_closed");
      }
    };
  }, [enabled, flowId, rejectAllPending, requestReload]);

  const submitOperations = useCallback(
    (
      operations: FlowOperation[],
      options?: { requestId?: string },
    ): Promise<CollaborationOperationAcceptedMessage> => {
      const ws = wsRef.current;
      const revision = currentRevisionRef.current;

      if (!ws || ws.readyState !== WebSocket.OPEN || revision === null) {
        return Promise.reject(new Error("Collaboration session is not ready"));
      }

      const requestId = options?.requestId ?? createRequestId();

      return new Promise((resolve, reject) => {
        pendingRef.current.set(requestId, { resolve, reject });
        ws.send(
          JSON.stringify({
            type: "operation.submit",
            request_id: requestId,
            base_revision: revision,
            operations,
          }),
        );
      });
    },
    [],
  );

  const sendSelectionUpdate = useCallback(
    (selected: CollaborationSelectionTarget | null) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return;
      }
      ws.send(
        JSON.stringify({
          type: "selection.update",
          selected,
        }),
      );
    },
    [],
  );

  useEffect(() => {
    mountedRef.current = true;

    if (!flowId || !enabled) {
      disconnect();
      return () => {
        mountedRef.current = false;
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      intentionalCloseRef.current = true;
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      rejectAllPending(new Error("Collaboration disconnected"));
    };
  }, [connect, disconnect, enabled, flowId, rejectAllPending]);

  return {
    status,
    connectionId,
    currentRevision,
    users,
    selections,
    isReady:
      status === "ready" && connectionId !== null && currentRevision !== null,
    submitOperations,
    sendSelectionUpdate,
    disconnect,
  };
}
