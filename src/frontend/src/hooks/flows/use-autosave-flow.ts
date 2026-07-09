import { useEffect, useRef } from "react";
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
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const autoSavingInterval = useFlowsManagerStore(
    (state) => state.autoSavingInterval,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const autoSaveFlow = useDebounce((flow?: FlowType) => {
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
      saveFlow(flow);
    }
  }, autoSavingInterval);

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
      saveFlow(pendingAutoSave.flow);
    }
  }, [autoSaving, can, currentFlowId, isLoading, saveFlow]);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
