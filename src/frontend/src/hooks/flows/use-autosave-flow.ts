import useFlowsManagerStore from "@/stores/flowsManagerStore";
import type { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const saveFlow = useSaveFlow();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const autoSavingInterval = useFlowsManagerStore(
    (state) => state.autoSavingInterval,
  );

  const autoSaveFlow = useDebounce((flow?: FlowType) => {
    if (autoSaving) {
      saveFlow(flow);
    }
  }, autoSavingInterval);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
