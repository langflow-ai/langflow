import { useEffect, useState } from "react";
import type { AssistantViewMode } from "../assistant-panel.types";

const ASSISTANT_VIEW_MODE_KEY = "langflow-assistant-view-mode";

interface UseAssistantViewModeReturn {
  viewMode: AssistantViewMode;
  setViewMode: (mode: AssistantViewMode) => void;
}

export function useAssistantViewMode(): UseAssistantViewModeReturn {
  const [viewMode, setViewMode] = useState<AssistantViewMode>(() => {
    try {
      const saved = localStorage.getItem(ASSISTANT_VIEW_MODE_KEY);
      return (saved as AssistantViewMode) || "floating";
    } catch {
      // localStorage may be unavailable (private browsing)
      return "floating";
    }
  });

  useEffect(() => {
    localStorage.setItem(ASSISTANT_VIEW_MODE_KEY, viewMode);
  }, [viewMode]);

  return { viewMode, setViewMode };
}
