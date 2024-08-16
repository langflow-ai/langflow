import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import { FlowType } from "@/types/flow";
import { useDebounce } from "../use-debounce";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const saveFlow = useSaveFlow();
  const shouldAutosave = process.env.LANGFLOW_AUTO_SAVING !== "false";

  const autoSaveFlow = shouldAutosave
    ? useDebounce((flow?: FlowType) => {
        saveFlow(flow);
      }, SAVE_DEBOUNCE_TIME)
    : () => {};

  return autoSaveFlow;
};

export default useAutoSaveFlow;
