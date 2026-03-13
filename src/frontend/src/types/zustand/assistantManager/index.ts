import type { FlowType, targetHandleType } from "../../flow";

export type AssistantManagerStoreType = {
  // Flow Context
  getFlowById: (id: string) => FlowType | undefined;
  flows: Array<FlowType> | undefined;
  setFlows: (flows: FlowType[]) => void;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  setCurrentFlow: (flow?: FlowType) => void;
  selectedFlowsComponentsCards: string[];
  setSelectedFlowsComponentsCards: (selected: string[]) => void;

  // Node Context
  selectedCompData: targetHandleType | undefined;
  setSelectedCompData: (compData: targetHandleType | undefined) => void;
  // Project context

  // UI state
  isFullscreen: boolean;
  setFullscreen: (isFullscreen: boolean) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
  assistantSidebarOpen: boolean;
  setAssistantSidebarOpen: (AssistantSideBarOpen: boolean) => void;

  // Chat state
  examples: Array<FlowType>;
  setExamples: (examples: FlowType[]) => void;
  newAssistantChat: boolean;
  setNewAssistantChat: (newChat: boolean) => void;
  selectedSession: string | undefined;
  setSelectedSession: (sessionId: string) => void;

  // General use
  healthCheckMaxRetries: number;
  setHealthCheckMaxRetries: (healthCheckMaxRetries: number) => void;
  resetStore: () => void;
};

export type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};
