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
  buildInverseFlowOperations,
  syncSavedFlowStateFromCanvas,
} from "@/hooks/flows/flow-operation-adapter";
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
  UpdateNodeEntry,
} from "@/types/flow-operations";

type UseFlowCollaborationEditingOptions = {
  flowId: string | undefined;
};

type QueuedOperationBatch = {
  operations: FlowOperation[];
  historyEntry?: CollaborationHistoryEntry;
  optimisticHistoryId?: number;
  onAccepted?: (acceptedForwardOps: FlowOperation[]) => void;
};

type UpdateNodesOperation = Extract<FlowOperation, { type: "update_nodes" }>;
type OptimisticHistoryEntry = CollaborationHistoryEntry & {
  optimisticHistoryId?: number;
};

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

function canCoalesceOperationBatch(batch: QueuedOperationBatch): boolean {
  const operation = getSingleUpdateNodesOperation(batch.operations);
  if (batch.onAccepted || !operation) {
    return false;
  }

  if (!batch.historyEntry) {
    return true;
  }

  const forwardOperation = getSingleUpdateNodesOperation(
    batch.historyEntry.forwardOps,
  );
  const inverseOperation = getSingleUpdateNodesOperation(
    batch.historyEntry.inverseOps,
  );
  return Boolean(forwardOperation && inverseOperation);
}

function updateEntryKey(update: UpdateNodeEntry): string {
  return `${update.id}:${JSON.stringify(update.path)}`;
}

function pathContains(
  ancestor: UpdateNodeEntry,
  descendant: UpdateNodeEntry,
): boolean {
  if (ancestor.id !== descendant.id) {
    return false;
  }
  if (ancestor.path.length > descendant.path.length) {
    return false;
  }
  return ancestor.path.every(
    (segment, index) => segment === descendant.path[index],
  );
}

function canonicalizeFieldUpdatesInOrder(
  updates: UpdateNodeEntry[],
): UpdateNodeEntry[] {
  const merged: UpdateNodeEntry[] = [];
  for (const update of updates) {
    const key = updateEntryKey(update);
    const nextUpdate = cloneDeep(update);
    for (let index = merged.length - 1; index >= 0; index -= 1) {
      const existing = merged[index];
      if (
        existing &&
        (updateEntryKey(existing) === key || pathContains(nextUpdate, existing))
      ) {
        merged.splice(index, 1);
      }
    }
    merged.push(nextUpdate);
  }
  return merged;
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

  const mergedUpdates = canonicalizeFieldUpdatesInOrder([
    ...currentOperation.updates,
    ...incomingOperation.updates,
  ]);

  const mergedForwardOps: FlowOperation[] = [
    {
      type: "update_nodes",
      updates: mergedUpdates,
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
  const inverseUpdates = canonicalizeFieldUpdatesInOrder([
    ...(incomingInverseOperation?.updates ?? []),
    ...(currentInverseOperation?.updates ?? []),
  ]);

  return {
    operations: mergedForwardOps,
    historyEntry: {
      forwardOps: mergedForwardOps,
      inverseOps: [
        {
          type: "update_nodes",
          updates: inverseUpdates,
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
  const undoHistoryRef = useRef<OptimisticHistoryEntry[]>([]);
  const redoHistoryRef = useRef<OptimisticHistoryEntry[]>([]);
  const nextOptimisticHistoryIdRef = useRef(1);
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

  const pushUndoHistory = useCallback(
    (entry: OptimisticHistoryEntry): OptimisticHistoryEntry => {
      const nextEntry = { ...entry };
      undoHistoryRef.current = [
        ...undoHistoryRef.current.slice(-MAX_COLLABORATION_HISTORY_SIZE + 1),
        nextEntry,
      ];
      return nextEntry;
    },
    [],
  );

  const replaceOptimisticHistoryEntry = useCallback(
    (optimisticHistoryId: number, entry: CollaborationHistoryEntry) => {
      const nextEntry = { ...entry, optimisticHistoryId };
      const replaceEntry = (historyEntry: OptimisticHistoryEntry) =>
        historyEntry.optimisticHistoryId === optimisticHistoryId
          ? nextEntry
          : historyEntry;

      undoHistoryRef.current = undoHistoryRef.current.map(replaceEntry);
      redoHistoryRef.current = redoHistoryRef.current.map(replaceEntry);
    },
    [],
  );

  const pushOptimisticUndoHistory = useCallback(
    (entry: CollaborationHistoryEntry): number => {
      const optimisticHistoryId = nextOptimisticHistoryIdRef.current;
      nextOptimisticHistoryIdRef.current += 1;
      pushUndoHistory({ ...entry, optimisticHistoryId });
      redoHistoryRef.current = [];
      return optimisticHistoryId;
    },
    [pushUndoHistory],
  );

  const ensureOptimisticHistory = useCallback(
    (batch: QueuedOperationBatch): QueuedOperationBatch => {
      if (!batch.historyEntry) {
        return batch;
      }
      if (batch.optimisticHistoryId != null) {
        replaceOptimisticHistoryEntry(
          batch.optimisticHistoryId,
          batch.historyEntry,
        );
        return batch;
      }
      return {
        ...batch,
        optimisticHistoryId: pushOptimisticUndoHistory(batch.historyEntry),
      };
    },
    [pushOptimisticUndoHistory, replaceOptimisticHistoryEntry],
  );

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
        if (batch.historyEntry && batch.optimisticHistoryId != null) {
          replaceOptimisticHistoryEntry(batch.optimisticHistoryId, {
            forwardOps: acceptedForwardOps,
            inverseOps: batch.historyEntry.inverseOps,
          });
        }
        batch.onAccepted?.(acceptedForwardOps);
      } catch {
        queuedOperationBatchesRef.current = [];
        await reloadFlowFromServer();
        return;
      }
    }
  }, [reloadFlowFromServer, replaceOptimisticHistoryEntry]);

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
      let batch: QueuedOperationBatch = {
        operations,
        historyEntry: options?.historyEntry,
      };

      if (canCoalesceOperationBatch(batch)) {
        const currentBatch = coalescedOperationBatchRef.current;
        batch = currentBatch
          ? {
              ...mergeUpdateNodeBatches(currentBatch, batch),
              optimisticHistoryId: currentBatch.optimisticHistoryId,
            }
          : batch;
        coalescedOperationBatchRef.current = ensureOptimisticHistory(batch);
        if (collaborationReadyRef.current) {
          scheduleCoalescedOperationFlush();
        }
        return;
      }

      flushCoalescedOperationBatch();
      queuedOperationBatchesRef.current.push(ensureOptimisticHistory(batch));
      scheduleDrainQueue();
    },
    [
      ensureOptimisticHistory,
      flushCoalescedOperationBatch,
      scheduleCoalescedOperationFlush,
      scheduleDrainQueue,
    ],
  );

  const enqueueHistoryAction = useCallback(
    (operations: FlowOperation[]) => {
      if (!operations.length || reloadingRef.current) {
        return false;
      }
      applyFlowOperationsToStore(operations);
      flushCoalescedOperationBatch();
      queuedOperationBatchesRef.current.push({ operations });
      scheduleDrainQueue();
      return true;
    },
    [flushCoalescedOperationBatch, scheduleDrainQueue],
  );

  const undoCollaborationOperations = useCallback(() => {
    const entry = undoHistoryRef.current.pop();
    if (!entry) {
      return;
    }
    const flowStore = useFlowStore.getState();
    const redoForwardOps = buildInverseFlowOperations(
      flowStore.nodes,
      flowStore.edges,
      flowStore.currentFlow?.data as Record<string, unknown> | undefined,
      entry.inverseOps,
    );
    if (enqueueHistoryAction(entry.inverseOps)) {
      if (redoForwardOps.length > 0) {
        redoHistoryRef.current.push({
          forwardOps: redoForwardOps,
          inverseOps: entry.inverseOps,
        });
      }
    } else {
      undoHistoryRef.current.push(entry);
    }
  }, [enqueueHistoryAction]);

  const redoCollaborationOperations = useCallback(() => {
    const entry = redoHistoryRef.current.pop();
    if (!entry) {
      return;
    }
    if (enqueueHistoryAction(entry.forwardOps)) {
      pushUndoHistory(entry);
    } else {
      redoHistoryRef.current.push(entry);
    }
  }, [enqueueHistoryAction, pushUndoHistory]);

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
