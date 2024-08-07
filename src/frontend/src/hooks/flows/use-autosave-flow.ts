import { SAVE_DEBOUNCE_TIME } from "@/constants/constants";
import { FlowType } from "@/types/flow";
import { debounce } from "lodash";
import { useMemo } from "react";
import useSaveFlow from "./use-save-flow";

const useAutoSaveFlow = () => {
  const saveFlow = useSaveFlow();

  const shouldAutosave = Boolean(process.env.LANGFLOW_AUTO_SAVE) ?? true;

  const autoSaveFlow = shouldAutosave
    ? useMemo(
        () =>
          debounce((flow?: FlowType) => {
            saveFlow(flow);
          }, SAVE_DEBOUNCE_TIME),
        [],
      )
    : () => {};

  return autoSaveFlow;
};

export default useAutoSaveFlow;
