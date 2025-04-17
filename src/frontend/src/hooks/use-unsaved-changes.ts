import useFlowStore from "../stores/flowStore";
import useFlowsManagerStore from "../stores/flowsManagerStore";
import { customStringify } from "../utils/reactflowUtils";

export function useUnsavedChanges() {
  const currentFlow = useFlowStore((state) => state.currentFlow);
  const savedFlow = useFlowsManagerStore((state) => state.currentFlow);

  if (!currentFlow || !savedFlow) {
    return false;
  }

  return customStringify(currentFlow) !== customStringify(savedFlow);
}
