import { tweakType } from "../components";
import { FlowType } from "../flow";

export type TabsContextType = {
  saveFlow: (flow: FlowType) => Promise<void>;
  save: () => void;
  tabId: string;
  isLoading: boolean;
  setTabId: (index: string) => void;
  flows: Array<FlowType>;
  removeFlow: (id: string) => void;
  addFlow: (
    flow?: FlowType,
    newProject?: Boolean
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
  uploadFlow: (newFlow?: boolean, file?: File) => Promise<String | undefined>;
  hardReset: () => void;
  getNodeId: (nodeType: string) => string;
  tabsState: TabsState;
  setTabsState: (state: TabsState) => void;
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  lastCopiedSelection: { nodes: any; edges: any } | null;
  setLastCopiedSelection: (selection: { nodes: any; edges: any }) => void;
  setTweak: (tweak: tweakType) => tweakType | void;
  getTweak: tweakType;
};

export type TabsState = {
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
