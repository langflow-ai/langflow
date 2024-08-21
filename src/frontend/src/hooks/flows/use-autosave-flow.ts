import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const saveFlow = useSaveFlow();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);

  const autoSaveFlow = useDebounce((flow?: FlowType) => {
    if (autoSaving) {
      saveFlow(flow);
    }
  }, SAVE_DEBOUNCE_TIME);

  return autoSaveFlow;
};

export default useAutoSaveFlow;
