import { useCallback, useEffect, useMemo, useRef } from "react";
import { usePermissions } from "@/contexts/permissionsContext";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { useTypesStore } from "@/stores/typesStore";
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
 * is certain, because a wrong pause silently stops persisting the user's work:
 *
 *  - the write is only rejected when a catalog policy actually blocks a key.
 *    `validate_catalog_policy_for_flow` returns early on an empty blocklist, so
 *    without a policy the save succeeds and there is nothing to pause for.
 *  - `blocked` means "no template for this type", which is also true of an
 *    uninstalled bundle, a flow imported from another install, and every
 *    code-bearing node while the registry is still loading. `templates` starts
 *    as `{}`, so a cold load would otherwise pause autosave and name every
 *    component in the flow.
 *
 * Anything short of both signals leaves autosave alone and lets the server
 * decide, which is the behaviour that existed before.
 */
const blockedComponentNames = (): string[] => {
  if (!useUtilityStore.getState().catalogGovernanceEnabled) {
    return [];
  }
  if (Object.keys(useTypesStore.getState().templates).length === 0) {
    return [];
  }
  return useFlowStore
    .getState()
    .componentsToUpdate.filter((component) => component.blocked)
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
