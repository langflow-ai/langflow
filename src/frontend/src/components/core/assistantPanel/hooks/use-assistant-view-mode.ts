import useAssistantManagerStore from "@/stores/assistantManagerStore";
import type { AssistantViewMode } from "../assistant-panel.types";

interface UseAssistantViewModeReturn {
  viewMode: AssistantViewMode;
  setViewMode: (mode: AssistantViewMode) => void;
}

export function useAssistantViewMode(): UseAssistantViewModeReturn {
  const viewMode = useAssistantManagerStore((state) => state.assistantViewMode);
  const setViewMode = useAssistantManagerStore(
    (state) => state.setAssistantViewMode,
  );

  return { viewMode, setViewMode };
}
