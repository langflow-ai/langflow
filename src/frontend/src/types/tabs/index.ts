import { XYPosition } from "reactflow";
import { tweakType } from "../components";
import { FlowType, NodeDataType } from "../flow";

export type FlowsContextType = {
  saveFlow: (flow: FlowType, silent?: boolean) => Promise<void>;
  tabId: string;
  isLoading: boolean;
  setTabId: (index: string) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition
  ) => Promise<String | undefined>;
  updateFlow: (newFlow: FlowType) => void;
  incrementNodeId: () => string;
  downloadFlow: (
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) => void;
  downloadFlows: () => void;
  uploadFlows: () => void;
  isBuilt: boolean;
  setIsBuilt: (state: boolean) => void;
  saveCurrentFlow: () => void;
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
  }) => Promise<String | never>;
  hardReset: () => void;
  getNodeId: (nodeType: string) => string;
  tabsState: FlowsState;
  setTabsState: (state: FlowsState) => void;
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  lastCopiedSelection: { nodes: any; edges: any } | null;
  setLastCopiedSelection: (selection: { nodes: any; edges: any }) => void;
  setTweak: (tweak: tweakType) => tweakType | void;
  getTweak: tweakType;
  saveComponent: (
    component: NodeDataType,
    override: boolean
  ) => Promise<String | undefined>;
  deleteComponent: (key: string) => void;
  version: string;
  nodesOnFlow: string;
  setNodesOnFlow: (nodes: string) => void;
};

export type FlowsState = {
  [key: string]: {
    isPending: boolean;
    formKeysData: {
      template?: string;
      input_keys?: Object;
      memory_keys?: Array<string>;
      handle_keys?: Array<string>;
    };
  };
};

export type errorsVarType = {
  title: string;
  list?: Array<string>;
};
