import { Edge, Node, Viewport } from "reactflow";
import { FlowType } from "../../flow";

export type FlowsManagerStoreType = {
  getFlowById: (id: string) => FlowType | undefined;
  flows: Array<FlowType>;
  allFlows: Array<FlowType>;
  setAllFlows: (flows: FlowType[]) => void;
  setFlows: (flows: FlowType[]) => void;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  setCurrentFlowId: (currentFlowId: string) => void;
  saveLoading: boolean;
  setSaveLoading: (saveLoading: boolean) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  refreshFlows: () => Promise<void>;
  saveFlow: (
    flow: FlowType,
    silent?: boolean,
    folderId?: string,
  ) => Promise<void> | undefined;
  saveFlowDebounce: (
    flow: FlowType,
    silent?: boolean,
    folderId?: string,
  ) => Promise<void> | undefined;
  autoSaveCurrentFlow: (
    nodes: Node[],
    edges: Edge[],
    viewport: Viewport,
  ) => void;
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
  examples: Array<FlowType>;
  setExamples: (examples: FlowType[]) => void;
  setCurrentFlow: (flow: FlowType) => void;
  setSearchFlowsComponents: (search: string) => void;
  searchFlowsComponents: string;
  selectedFlowsComponentsCards: string[];
  setSelectedFlowsComponentsCards: (selected: string[]) => void;
};

export type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};
