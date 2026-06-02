import { cloneDeep } from "lodash";
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
import type {
  CollaborationPresenceUser,
  CollaborationSelectionTarget,
  CollaborationUserSelection,
} from "@/types/flow-collaboration";
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

type UpdateNodesOperation = Extract<FlowOperation, { type: "update_nodes" }>;

const MAX_COLLABORATION_HISTORY_SIZE = 100;
const UPDATE_NODES_COALESCE_MS = 300;

function getSingleUpdateNodesOperation(
  operations: FlowOperation[],
): UpdateNodesOperation | null {
  const [operation] = operations;
  return operations.length === 1 && operation?.type === "update_nodes"
    ? operation
    : null;
}

function isUpdateNodesOnly(operations: FlowOperation[]): boolean {
  return getSingleUpdateNodesOperation(operations) !== null;
}

function canCoalesceOperationBatch(batch: QueuedOperationBatch): boolean {
  if (batch.onAccepted || !isUpdateNodesOnly(batch.operations)) {
    return false;
  }

  if (!batch.historyEntry) {
    return true;
  }

  return (
    isUpdateNodesOnly(batch.historyEntry.forwardOps) &&
    isUpdateNodesOnly(batch.historyEntry.inverseOps)
  );
}

function mergeUpdateNodeBatches(
  current: QueuedOperationBatch,
  incoming: QueuedOperationBatch,
): QueuedOperationBatch {
  const currentOperation = getSingleUpdateNodesOperation(current.operations);
  const incomingOperation = getSingleUpdateNodesOperation(incoming.operations);
  if (!currentOperation || !incomingOperation) {
    return incoming;
  }

  const mergedNodesById = new Map(
    currentOperation.nodes.map((node) => [node.id, cloneDeep(node)]),
  );
  for (const node of incomingOperation.nodes) {
    mergedNodesById.set(node.id, cloneDeep(node));
  }

  const mergedForwardOps: FlowOperation[] = [
    {
      type: "update_nodes",
      nodes: Array.from(mergedNodesById.values()),
    },
  ];

  if (!current.historyEntry && !incoming.historyEntry) {
    return { operations: mergedForwardOps };
  }

  const currentInverseOperation = current.historyEntry
    ? getSingleUpdateNodesOperation(current.historyEntry.inverseOps)
    : null;
  const incomingInverseOperation = incoming.historyEntry
    ? getSingleUpdateNodesOperation(incoming.historyEntry.inverseOps)
    : null;
  const inverseNodesById = new Map(
    currentInverseOperation
      ? currentInverseOperation.nodes.map((node) => [node.id, cloneDeep(node)])
      : [],
  );

  if (incomingInverseOperation) {
    for (const node of incomingInverseOperation.nodes) {
      if (!inverseNodesById.has(node.id)) {
        inverseNodesById.set(node.id, cloneDeep(node));
      }
    }
  }

  return {
    operations: mergedForwardOps,
    historyEntry: {
      forwardOps: cloneDeep(mergedForwardOps),
      inverseOps: [
        {
          type: "update_nodes",
          nodes: Array.from(inverseNodesById.values()),
        },
      ],
    },
  };
}

export type UseFlowCollaborationEditingReturn = {
  betaEnabled: boolean;
  setBetaEnabled: (enabled: boolean) => Promise<void>;
  users: CollaborationPresenceUser[];
  selections: CollaborationUserSelection[];
  sendSelectionUpdate: (selected: CollaborationSelectionTarget | null) => void;
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
  const coalescedOperationBatchRef = useRef<QueuedOperationBatch | null>(null);
  const coalescedOperationTimerRef = useRef<ReturnType<
    typeof setTimeout
  > | null>(null);
  const undoHistoryRef = useRef<CollaborationHistoryEntry[]>([]);
  const redoHistoryRef = useRef<CollaborationHistoryEntry[]>([]);
  const collaborationReadyRef = useRef(false);
  const reloadingRef = useRef(false);

  const clearCollaborationHistory = useCallback(() => {
    undoHistoryRef.current = [];
    redoHistoryRef.current = [];
  }, []);

  const clearCoalescedOperationBatch = useCallback(() => {
    if (coalescedOperationTimerRef.current) {
      clearTimeout(coalescedOperationTimerRef.current);
      coalescedOperationTimerRef.current = null;
    }
    coalescedOperationBatchRef.current = null;
  }, []);

  const flushCoalescedOperationBatch = useCallback(() => {
    if (coalescedOperationTimerRef.current) {
      clearTimeout(coalescedOperationTimerRef.current);
      coalescedOperationTimerRef.current = null;
    }

    const batch = coalescedOperationBatchRef.current;
    if (!batch) {
      return false;
    }

    coalescedOperationBatchRef.current = null;
    queuedOperationBatchesRef.current.push(batch);
    return true;
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
    clearCoalescedOperationBatch();
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
  }, [
    applyFlowToCanvas,
    clearCoalescedOperationBatch,
    clearCollaborationHistory,
    flowId,
    getFlow,
  ]);

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

  const scheduleDrainQueue = useCallback(() => {
    if (!collaborationReadyRef.current) {
      return;
    }

    submitChainRef.current = submitChainRef.current
      .catch(() => {})
      .then(drainQueue);
  }, [drainQueue]);

  const scheduleCoalescedOperationFlush = useCallback(() => {
    if (coalescedOperationTimerRef.current) {
      clearTimeout(coalescedOperationTimerRef.current);
    }

    coalescedOperationTimerRef.current = setTimeout(() => {
      coalescedOperationTimerRef.current = null;
      if (flushCoalescedOperationBatch()) {
        scheduleDrainQueue();
      }
    }, UPDATE_NODES_COALESCE_MS);
  }, [flushCoalescedOperationBatch, scheduleDrainQueue]);

  const enqueueOperations = useCallback(
    (operations: FlowOperation[], options?: FlowOperationEmitOptions) => {
      if (!operations.length || reloadingRef.current) {
        return;
      }
      const batch: QueuedOperationBatch = {
        operations,
        historyEntry: options?.historyEntry,
      };

      if (canCoalesceOperationBatch(batch)) {
        coalescedOperationBatchRef.current = coalescedOperationBatchRef.current
          ? mergeUpdateNodeBatches(coalescedOperationBatchRef.current, batch)
          : batch;
        if (collaborationReadyRef.current) {
          scheduleCoalescedOperationFlush();
        }
        return;
      }

      flushCoalescedOperationBatch();
      queuedOperationBatchesRef.current.push(batch);
      scheduleDrainQueue();
    },
    [
      flushCoalescedOperationBatch,
      scheduleCoalescedOperationFlush,
      scheduleDrainQueue,
    ],
  );

  const enqueueHistoryAction = useCallback(
    (operations: FlowOperation[], onAccepted: () => void) => {
      if (!operations.length || reloadingRef.current) {
        return;
      }
      applyFlowOperationsToStore(operations);
      flushCoalescedOperationBatch();
      queuedOperationBatchesRef.current.push({ operations, onAccepted });
      scheduleDrainQueue();
    },
    [flushCoalescedOperationBatch, scheduleDrainQueue],
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
    if (flushCoalescedOperationBatch()) {
      scheduleDrainQueue();
    }
    await submitChainRef.current;
    if (queuedOperationBatchesRef.current.length > 0) {
      if (!collaborationReadyRef.current) {
        throw new Error("Collaboration session is not ready");
      }
      await drainQueue();
    }
    syncSavedFlowStateFromCanvas();
  }, [drainQueue, flushCoalescedOperationBatch, scheduleDrainQueue]);

  const collaboration = useFlowCollaboration({
    flowId,
    enabled: betaEnabled && Boolean(flowId),
    onRemoteOperation: (message) => {
      applyRemoteFlowOperations(message.forward_ops);
      invalidateHistoryForRemoteOperations(message.forward_ops);
    },
    onReloadRequired: () => {
      queuedOperationBatchesRef.current = [];
      clearCoalescedOperationBatch();
      submitChainRef.current = Promise.resolve();
      clearCollaborationHistory();
      void reloadFlowFromServer();
    },
  });

  submitOperationsRef.current = collaboration.submitOperations;
  collaborationReadyRef.current = collaboration.isReady;

  useEffect(() => {
    if (!collaboration.isReady) {
      return;
    }
    if (
      flushCoalescedOperationBatch() ||
      queuedOperationBatchesRef.current.length > 0
    ) {
      scheduleDrainQueue();
    }
  }, [collaboration.isReady, flushCoalescedOperationBatch, scheduleDrainQueue]);

  useEffect(() => {
    if (!betaEnabled) {
      clearCoalescedOperationBatch();
    }
  }, [betaEnabled, clearCoalescedOperationBatch]);

  useEffect(() => clearCoalescedOperationBatch, [clearCoalescedOperationBatch]);

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
    selections: collaboration.selections,
    sendSelectionUpdate: collaboration.sendSelectionUpdate,
    isCollaborationReady: collaboration.isReady,
    collaborationStatus: collaboration.status,
  };
}
