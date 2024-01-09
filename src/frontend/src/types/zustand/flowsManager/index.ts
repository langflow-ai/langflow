import { Edge, Node, Viewport, XYPosition } from "reactflow";
import { FlowType } from "../../flow";

export type FlowsManagerStoreType = {
  flows: Array<FlowType>;
  setFlows: (flows: FlowType[]) => void;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  setCurrentFlowId: (currentFlowId: string) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  refreshFlows: () => Promise<void>;
  saveFlow: (flow: FlowType, silent?: boolean) => Promise<void>;
  autoSaveCurrentFlow: (
    nodes: Node[],
    edges: Edge[],
    viewport: Viewport
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
    isComponent?: boolean;
    position?: XYPosition;
  }) => Promise<string | never>;
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition
  ) => Promise<string | undefined>;
  deleteComponent: (key: string) => Promise<void>;
  removeFlow: (id: string) => Promise<void>;
  saveComponent: (
    component: any,
    override: boolean
  ) => Promise<string | undefined>;
  undo: () => void;
  redo: () => void;
  takeSnapshot: () => void;
};

export type UseUndoRedoOptions = {
  maxHistorySize: number;
  enableShortcuts: boolean;
};
