import { usePermissions } from "@/contexts/permissionsContext";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const { can, isLoading } = usePermissions();
  const saveFlow = useSaveFlow();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const autoSavingInterval = useFlowsManagerStore(
    (state) => state.autoSavingInterval,
  );
  const currentFlowId = useFlowsManagerStore((state) => state.currentFlowId);

  const autoSaveFlow = useDebounce((flow?: FlowType) => {
    const flowId = flow?.id ?? currentFlowId;
    if (autoSaving && !isLoading && can(flowId, "write")) {
      saveFlow(flow);
    }
  }, autoSavingInterval);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
