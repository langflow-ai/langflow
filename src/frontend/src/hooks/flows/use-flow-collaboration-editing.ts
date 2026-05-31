import { useCallback, useEffect, useRef, useState } from "react";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import {
  readCollaborationOperationBetaEnabled,
  writeCollaborationOperationBetaEnabled,
} from "@/hooks/flows/collaboration-operation-beta";
import {
  applyFlowOperationsToStore,
  applyRemoteFlowOperations,
  syncSavedFlowStateFromCanvas,
} from "@/hooks/flows/flow-operation-adapter";
import {
  collectFlowOperationTouches,
  flowOperationTouchesIntersect,
} from "@/hooks/flows/flow-operation-diff";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import { useFlowCollaboration } from "@/hooks/flows/use-flow-collaboration";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { CollaborationPresenceUser } from "@/types/flow-collaboration";
import type {
  CollaborationHistoryEntry,
  FlowOperation,
  FlowOperationEmitOptions,
} from "@/types/flow-operations";

type UseFlowCollaborationEditingOptions = {
  flowId: string | undefined;
};

type QueuedOperationBatch = {
  operations: FlowOperation[];
  historyEntry?: CollaborationHistoryEntry;
  onAccepted?: (acceptedForwardOps: FlowOperation[]) => void;
};

const MAX_COLLABORATION_HISTORY_SIZE = 100;

export type UseFlowCollaborationEditingReturn = {
  betaEnabled: boolean;
  setBetaEnabled: (enabled: boolean) => Promise<void>;
  users: CollaborationPresenceUser[];
  isCollaborationReady: boolean;
  collaborationStatus: ReturnType<typeof useFlowCollaboration>["status"];
};

export function useFlowCollaborationEditing({
  flowId,
}: UseFlowCollaborationEditingOptions): UseFlowCollaborationEditingReturn {
  const [betaEnabled, setBetaEnabledState] = useState(
    readCollaborationOperationBetaEnabled,
  );
  const applyFlowToCanvas = useApplyFlowToCanvas();
  const { mutateAsync: getFlow } = useGetFlow();

  const submitChainRef = useRef<Promise<void>>(Promise.resolve());
  const queuedOperationBatchesRef = useRef<QueuedOperationBatch[]>([]);
  const undoHistoryRef = useRef<CollaborationHistoryEntry[]>([]);
  const redoHistoryRef = useRef<CollaborationHistoryEntry[]>([]);
  const collaborationReadyRef = useRef(false);
  const reloadingRef = useRef(false);

  const clearCollaborationHistory = useCallback(() => {
    undoHistoryRef.current = [];
    redoHistoryRef.current = [];
  }, []);

  const pushUndoHistory = useCallback((entry: CollaborationHistoryEntry) => {
    undoHistoryRef.current = [
      ...undoHistoryRef.current.slice(-MAX_COLLABORATION_HISTORY_SIZE + 1),
      entry,
    ];
  }, []);

  const reloadFlowFromServer = useCallback(async () => {
    if (!flowId) {
      return;
    }
    queuedOperationBatchesRef.current = [];
    submitChainRef.current = Promise.resolve();
    clearCollaborationHistory();
    reloadingRef.current = true;
    useFlowStore.setState({ isApplyingRemoteOperations: true });
    try {
      const response = await getFlow({ id: flowId });
      if (useFlowsManagerStore.getState().currentFlowId !== flowId) {
        return;
      }
      applyFlowToCanvas(response);
      syncSavedFlowStateFromCanvas();
      useFlowsManagerStore.getState().clearUndoRedoHistory?.(flowId);
    } finally {
      reloadingRef.current = false;
      useFlowStore.setState({ isApplyingRemoteOperations: false });
    }
  }, [applyFlowToCanvas, clearCollaborationHistory, flowId, getFlow]);

  const submitOperationsRef = useRef<
    ReturnType<typeof useFlowCollaboration>["submitOperations"] | null
  >(null);

  const drainQueue = useCallback(async () => {
    if (
      !collaborationReadyRef.current ||
      reloadingRef.current ||
      queuedOperationBatchesRef.current.length === 0
    ) {
      return;
    }

    const submit = submitOperationsRef.current;
    if (!submit) {
      return;
    }

    while (
      collaborationReadyRef.current &&
      !reloadingRef.current &&
      queuedOperationBatchesRef.current.length > 0
    ) {
      const batch = queuedOperationBatchesRef.current.shift();
      if (!batch) {
        return;
      }
      try {
        const accepted = await submit(batch.operations);
        const acceptedForwardOps =
          accepted.forward_ops.length > 0
            ? accepted.forward_ops
            : batch.operations;
        if (batch.historyEntry) {
          pushUndoHistory({
            forwardOps: acceptedForwardOps,
            inverseOps: batch.historyEntry.inverseOps,
          });
          redoHistoryRef.current = [];
        }
        batch.onAccepted?.(acceptedForwardOps);
      } catch {
        queuedOperationBatchesRef.current = [];
        await reloadFlowFromServer();
        return;
      }
    }
  }, [pushUndoHistory, reloadFlowFromServer]);

  const enqueueOperations = useCallback(
    (operations: FlowOperation[], options?: FlowOperationEmitOptions) => {
      if (!operations.length || reloadingRef.current) {
        return;
      }
      queuedOperationBatchesRef.current.push({
        operations,
        historyEntry: options?.historyEntry,
      });
      if (!collaborationReadyRef.current) {
        return;
      }
      submitChainRef.current = submitChainRef.current
        .catch(() => {})
        .then(drainQueue);
    },
    [drainQueue],
  );

  const enqueueHistoryAction = useCallback(
    (operations: FlowOperation[], onAccepted: () => void) => {
      if (!operations.length || reloadingRef.current) {
        return;
      }
      applyFlowOperationsToStore(operations);
      queuedOperationBatchesRef.current.push({ operations, onAccepted });
      if (!collaborationReadyRef.current) {
        return;
      }
      submitChainRef.current = submitChainRef.current
        .catch(() => {})
        .then(drainQueue);
    },
    [drainQueue],
  );

  const undoCollaborationOperations = useCallback(() => {
    const entry = undoHistoryRef.current.pop();
    if (!entry) {
      return;
    }
    enqueueHistoryAction(entry.inverseOps, () => {
      redoHistoryRef.current.push(entry);
    });
  }, [enqueueHistoryAction]);

  const redoCollaborationOperations = useCallback(() => {
    const entry = redoHistoryRef.current.pop();
    if (!entry) {
      return;
    }
    enqueueHistoryAction(entry.forwardOps, () => {
      pushUndoHistory(entry);
    });
  }, [enqueueHistoryAction, pushUndoHistory]);

  const invalidateHistoryForRemoteOperations = useCallback(
    (operations: FlowOperation[]) => {
      const remoteTouches = collectFlowOperationTouches(operations);
      const isStillValid = (entry: CollaborationHistoryEntry) => {
        const entryTouches = collectFlowOperationTouches([
          ...entry.forwardOps,
          ...entry.inverseOps,
        ]);
        return !flowOperationTouchesIntersect(remoteTouches, entryTouches);
      };

      undoHistoryRef.current = undoHistoryRef.current.filter(isStillValid);
      redoHistoryRef.current = redoHistoryRef.current.filter(isStillValid);
    },
    [],
  );

  const flushCollaborationSave = useCallback(async () => {
    await submitChainRef.current;
    if (queuedOperationBatchesRef.current.length > 0) {
      if (!collaborationReadyRef.current) {
        throw new Error("Collaboration session is not ready");
      }
      await drainQueue();
    }
    syncSavedFlowStateFromCanvas();
  }, [drainQueue]);

  const collaboration = useFlowCollaboration({
    flowId,
    enabled: betaEnabled && Boolean(flowId),
    onRemoteOperation: (message) => {
      applyRemoteFlowOperations(message.forward_ops);
      invalidateHistoryForRemoteOperations(message.forward_ops);
    },
    onReloadRequired: () => {
      queuedOperationBatchesRef.current = [];
      submitChainRef.current = Promise.resolve();
      clearCollaborationHistory();
      void reloadFlowFromServer();
    },
  });

  submitOperationsRef.current = collaboration.submitOperations;
  collaborationReadyRef.current = collaboration.isReady;

  useEffect(() => {
    if (
      !collaboration.isReady ||
      queuedOperationBatchesRef.current.length === 0
    ) {
      return;
    }
    submitChainRef.current = submitChainRef.current
      .catch(() => {})
      .then(drainQueue);
  }, [collaboration.isReady, drainQueue]);

  useEffect(() => {
    useFlowStore.setState({
      collaborationOperationMode: betaEnabled,
      onCollaborationOperations: betaEnabled ? enqueueOperations : undefined,
      undoCollaborationOperations: betaEnabled
        ? undoCollaborationOperations
        : undefined,
      redoCollaborationOperations: betaEnabled
        ? redoCollaborationOperations
        : undefined,
      flushCollaborationSave: betaEnabled ? flushCollaborationSave : undefined,
    });

    return () => {
      useFlowStore.setState({
        collaborationOperationMode: false,
        onCollaborationOperations: undefined,
        undoCollaborationOperations: undefined,
        redoCollaborationOperations: undefined,
        flushCollaborationSave: undefined,
      });
    };
  }, [
    betaEnabled,
    enqueueOperations,
    flushCollaborationSave,
    redoCollaborationOperations,
    undoCollaborationOperations,
  ]);

  const setBetaEnabled = useCallback(
    async (enabled: boolean) => {
      writeCollaborationOperationBetaEnabled(enabled);
      setBetaEnabledState(enabled);
      if (flowId) {
        await reloadFlowFromServer();
      }
    },
    [flowId, reloadFlowFromServer],
  );

  return {
    betaEnabled,
    setBetaEnabled,
    users: collaboration.users,
    isCollaborationReady: collaboration.isReady,
    collaborationStatus: collaboration.status,
  };
}
