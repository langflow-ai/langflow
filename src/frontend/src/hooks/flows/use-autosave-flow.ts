import { useCallback, useEffect, useMemo, useRef } from "react";
import { isBlockedByCatalogPolicy } from "@/CustomNodes/helpers/check-code-validity";
import { usePermissions } from "@/contexts/permissionsContext";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useUtilityStore } from "@/stores/utilityStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

type PendingAutoSave = {
  flow?: FlowType;
  flowId: string | undefined;
};

/**
 * Components the server will refuse to persist, if any.
 *
 * Autosaving a flow the server rejects retries a write that can never succeed,
 * so opening an affected flow produced a stream of failed requests before the
 * user had touched anything. Pausing instead is only safe where the rejection
 * is certain, because a wrong pause silently stops persisting the user's work.
 *
 * `blocked` alone is not that certainty: it means "no template for this type",
 * which is equally an uninstalled bundle, a flow imported from another
 * install, and a component the user wrote themselves. Only the policy's own
 * identities separate the one the server will reject from the three it accepts,
 * so this asks whether the policy names this component, not whether a policy
 * exists.
 */
const blockedComponentNames = (): string[] => {
  const { blockedComponentTypes } = useUtilityStore.getState();
  if (blockedComponentTypes.size === 0) {
    return [];
  }
  return useFlowStore
    .getState()
    .componentsToUpdate.filter(
      (component) =>
        component.blocked &&
        isBlockedByCatalogPolicy(blockedComponentTypes, component.type),
    )
    .map((component) => component.display_name ?? component.id);
};

const useAutoSaveFlow = () => {
  const { can, isLoading } = usePermissions();
  const setErrorData = useAlertStore((state) => state.setErrorData);
  const reportedBlockedRef = useRef(false);

  // Report the pause once per occurrence: the user needs to know the flow is
  // no longer being saved, but not on every debounce tick.
  const pauseForBlockedComponents = useCallback(() => {
    const names = blockedComponentNames();
    if (names.length === 0) {
      reportedBlockedRef.current = false;
      return false;
    }
    if (!reportedBlockedRef.current) {
      reportedBlockedRef.current = true;
      setErrorData({
        title: "Flow not saved",
        list: [
          `Saving is paused while this flow uses components disabled by an administrator: ${names.join(", ")}. Remove them to resume saving.`,
        ],
      });
    }
    return true;
  }, [setErrorData]);
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
    if (pauseForBlockedComponents()) {
      // Hold the edit rather than discard it, so it still lands once the
      // blocking component is removed.
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
    if (pauseForBlockedComponents()) {
      return;
    }
    if (can(flowId, "write")) {
      pendingAutoSaveRef.current = null;
      void enqueueSave(pendingAutoSave.flow);
    }
  }, [
    autoSaving,
    can,
    currentFlowId,
    enqueueSave,
    isLoading,
    pauseForBlockedComponents,
  ]);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
