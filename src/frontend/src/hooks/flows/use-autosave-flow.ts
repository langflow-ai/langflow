import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePermissions } from "@/contexts/permissionsContext";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

type PendingAutoSave = {
  flow?: FlowType;
  flowId: string | undefined;
};

const useAutoSaveFlow = () => {
  const { can, isLoading } = usePermissions();
  const saveFlow = useSaveFlow();
  const pendingAutoSaveRef = useRef<PendingAutoSave | null>(null);
  const saveQueueTailRef = useRef<Promise<void>>(Promise.resolve());
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const autoSavingInterval = useFlowsManagerStore(
    (state) => state.autoSavingInterval,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const enqueueSave = useCallback(
    (flow?: FlowType): Promise<void> => {
      const queuedSave = saveQueueTailRef.current.then(() => saveFlow(flow));
      // Keep the tail fulfilled after a failed save so later edits still get a
      // chance to persist. The queuedSave returned to the immediate caller
      // retains the original rejection while the shared barrier tracks settle.
      saveQueueTailRef.current = queuedSave.catch(() => undefined);
      return queuedSave;
    },
    [saveFlow],
  );

  const debouncedAutoSave = useDebounce((flow?: FlowType) => {
    const flowId = flow?.id ?? currentFlowId;
    if (!autoSaving) {
      pendingAutoSaveRef.current = null;
      return;
    }
    if (isLoading) {
      pendingAutoSaveRef.current = { flow, flowId };
      return;
    }
    if (can(flowId, "write")) {
      pendingAutoSaveRef.current = null;
      return enqueueSave(flow);
    }
  }, autoSavingInterval);

  const autoSaveFlow = useMemo(() => {
    const queuedAutoSave = (flow?: FlowType) => debouncedAutoSave(flow);
    queuedAutoSave.cancel = () => debouncedAutoSave.cancel?.();
    queuedAutoSave.flush = async (): Promise<void> => {
      // flush() invokes a pending debounce callback synchronously, which adds
      // its save to saveQueueTailRef before we capture and await the tail.
      debouncedAutoSave.flush?.();
      await saveQueueTailRef.current;
    };
    return queuedAutoSave;
  }, [debouncedAutoSave]);

  useEffect(() => {
    const pendingAutoSave = pendingAutoSaveRef.current;
    if (!pendingAutoSave || isLoading) {
      return;
    }
    if (!autoSaving) {
      pendingAutoSaveRef.current = null;
      return;
    }
    const flowId =
      pendingAutoSave.flowId ?? pendingAutoSave.flow?.id ?? currentFlowId;
    if (can(flowId, "write")) {
      pendingAutoSaveRef.current = null;
      void enqueueSave(pendingAutoSave.flow);
    }
  }, [autoSaving, can, currentFlowId, enqueueSave, isLoading]);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
