import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import useFlowsManagerStore from "@/stores/flowsManagerStore";
import { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const saveFlow = useSaveFlow();
  const autoSaving = useFlowsManagerStore((state) => state.autoSaving);
  const autoSavingInterval = useFlowsManagerStore(
    (state) => state.autoSavingInterval,
  );

  const autoSaveFlow = autoSaving
    ? useDebounce((flow?: FlowType) => {
        saveFlow(flow);
      }, autoSavingInterval)
    : () => {};

  return autoSaveFlow;
};

export default useAutoSaveFlow;
