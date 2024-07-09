import { Edge, Node, Viewport, XYPosition } from "reactflow";
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
  uploadFlows: () => Promise<void>;
  uploadFlow: ({
    newProject,
    file,
    isComponent,
    position,
  }: {
    newProject: boolean;
    file?: File;
    isComponent: boolean | null;
    position?: XYPosition;
  }) => Promise<string | never>;
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition,
    fromDragAndDrop?: boolean,
  ) => Promise<string | undefined>;
  deleteComponent: (key: string) => Promise<void>;
  removeFlow: (id: string | string[]) => Promise<void>;
  saveComponent: (
    component: any,
    override: boolean,
  ) => Promise<string | undefined>;
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
