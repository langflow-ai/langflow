import { FlowType } from "../../flow";

export type FlowsManagerStoreType = {
  autoSaving: boolean;
  setAutoSaving: (autoSaving: boolean) => void;
  getFlowById: (id: string) => FlowType | undefined;
  flows: Array<FlowType> | undefined;
  setFlows: (flows: FlowType[]) => void;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  saveLoading: boolean;
  setSaveLoading: (saveLoading: boolean) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
  examples: Array<FlowType>;
  setExamples: (examples: FlowType[]) => void;
  setCurrentFlow: (flow?: FlowType) => void;
  setSearchFlowsComponents: (search: string) => void;
  searchFlowsComponents: string;
  selectedFlowsComponentsCards: string[];
  setSelectedFlowsComponentsCards: (selected: string[]) => void;
  autoSavingInterval: number;
  setAutoSavingInterval: (autoSavingInterval: number) => void;
  healthCheckMaxRetries: number;
  setHealthCheckMaxRetries: (healthCheckMaxRetries: number) => void;
  flowToCanvas: FlowType | null;
  setFlowToCanvas: (flowToCanvas: FlowType | null) => Promise<void>;
  IOModalOpen: boolean;
  setIOModalOpen: (IOModalOpen: boolean) => void;
};

export type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};
