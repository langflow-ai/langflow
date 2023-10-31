import { FlowType } from "../flow";

export type FlowsContextType = {
  saveFlow: (flow: FlowType, silent?: boolean) => Promise<void>;
  tabId: string;
  isLoading: boolean;
  setTabId: (index: string) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (
    newProject: boolean,
    flow?: FlowType
  ) => Promise<String | undefined>;
  updateFlow: (newFlow: FlowType) => void;
  downloadFlows: () => void;
  uploadFlows: () => void;
  isBuilt: boolean;
  setIsBuilt: (state: boolean) => void;
  uploadFlow: (newFlow: boolean, file?: File) => Promise<String | undefined>;
  hardReset: () => void;
  getNodeId: (nodeType: string) => string;
  tabsState: FlowsState;
  setTabsState: (state: FlowsState) => void;
  lastCopiedSelection: { nodes: any; edges: any } | null;
  setLastCopiedSelection: (selection: { nodes: any; edges: any }) => void;
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
