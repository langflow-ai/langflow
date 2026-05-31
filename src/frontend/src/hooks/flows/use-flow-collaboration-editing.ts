import { useCallback, useEffect, useRef, useState } from "react";
import { useGetFlow } from "@/controllers/API/queries/flows/use-get-flow";
import {
  readCollaborationOperationBetaEnabled,
  writeCollaborationOperationBetaEnabled,
} from "@/hooks/flows/collaboration-operation-beta";
import {
  applyRemoteFlowOperations,
  syncSavedFlowStateFromCanvas,
} from "@/hooks/flows/flow-operation-adapter";
import useApplyFlowToCanvas from "@/hooks/flows/use-apply-flow-to-canvas";
import { useFlowCollaboration } from "@/hooks/flows/use-flow-collaboration";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { CollaborationPresenceUser } from "@/types/flow-collaboration";
import type { FlowOperation } from "@/types/flow-operations";

type UseFlowCollaborationEditingOptions = {
  flowId: string | undefined;
};

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
  const queuedOperationsRef = useRef<FlowOperation[]>([]);
  const collaborationReadyRef = useRef(false);
  const reloadingRef = useRef(false);

  const reloadFlowFromServer = useCallback(async () => {
    if (!flowId) {
      return;
    }
    queuedOperationsRef.current = [];
    submitChainRef.current = Promise.resolve();
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
  }, [applyFlowToCanvas, flowId, getFlow]);

  const submitOperationsRef = useRef<
    ((operations: FlowOperation[]) => Promise<unknown>) | null
  >(null);

  const drainQueue = useCallback(async () => {
    if (
      !collaborationReadyRef.current ||
      reloadingRef.current ||
      queuedOperationsRef.current.length === 0
    ) {
      return;
    }

    const submit = submitOperationsRef.current;
    if (!submit) {
      return;
    }

    const batch = queuedOperationsRef.current.splice(
      0,
      queuedOperationsRef.current.length,
    );
    try {
      await submit(batch);
    } catch {
      queuedOperationsRef.current = [];
      await reloadFlowFromServer();
    }
  }, [reloadFlowFromServer]);

  const enqueueOperations = useCallback(
    (operations: FlowOperation[]) => {
      if (!operations.length || reloadingRef.current) {
        return;
      }
      queuedOperationsRef.current.push(...operations);
      if (!collaborationReadyRef.current) {
        return;
      }
      submitChainRef.current = submitChainRef.current
        .catch(() => {})
        .then(drainQueue);
    },
    [drainQueue],
  );

  const flushCollaborationSave = useCallback(async () => {
    await submitChainRef.current;
    if (queuedOperationsRef.current.length > 0) {
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
    },
    onReloadRequired: () => {
      queuedOperationsRef.current = [];
      submitChainRef.current = Promise.resolve();
      void reloadFlowFromServer();
    },
  });

  submitOperationsRef.current = collaboration.submitOperations;
  collaborationReadyRef.current = collaboration.isReady;

  useEffect(() => {
    if (!collaboration.isReady || queuedOperationsRef.current.length === 0) {
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
      flushCollaborationSave: betaEnabled ? flushCollaborationSave : undefined,
    });

    return () => {
      useFlowStore.setState({
        collaborationOperationMode: false,
        onCollaborationOperations: undefined,
        flushCollaborationSave: undefined,
      });
    };
  }, [betaEnabled, enqueueOperations, flushCollaborationSave]);

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
