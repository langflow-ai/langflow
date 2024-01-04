import { Edge, EdgeChange, Node, NodeChange, XYPosition } from "reactflow";
import { tweakType } from "../components";
import { FlowType, NodeDataType } from "../flow";

type OnChange<ChangesType> = (changes: ChangesType[]) => void;

export type FlowsContextType = {
  //keep
  saveFlow: (flow?: FlowType, silent?: boolean) => Promise<void>;
  tabId: string;
  //keep
  isLoading: boolean;
  setTabId: (index: string) => void;
  //keep
  flows: Array<FlowType>;
  deleteNode: (idx: string | Array<string>) => void;
  deleteEdge: (idx: string | Array<string>) => void;
  //keep
  removeFlow: (id: string) => void;
  //keep
  addFlow: (
    newProject: boolean,
    flow?: FlowType,
    override?: boolean,
    position?: XYPosition
  ) => Promise<String | undefined>;
  incrementNodeId: () => string;
  downloadFlow: (
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) => void;
  //keep
  downloadFlows: () => void;
  //keep
  uploadFlows: () => void;
  isBuilt: boolean;
  setIsBuilt: (state: boolean) => void;
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
  getNodeId: (nodeType: string) => string;
  isPending: boolean;
  setPending: (pending: boolean) => void;
  tabsState: FlowsState;
  setTabsState: (
    update: FlowsState | ((oldState: FlowsState) => FlowsState)
  ) => void;
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
  nodes: Array<Node>;
  setNodes: (update: Node[] | ((oldState: Node[]) => Node[])) => void;
  setNode: (id: string, update: Node | ((oldState: Node) => Node)) => void;
  getNode: (id: string) => Node | undefined;
  onNodesChange: OnChange<NodeChange>;
  edges: Array<Edge>;
  setEdges: (update: Edge[] | ((oldState: Edge[]) => Edge[])) => void;
  onEdgesChange: OnChange<EdgeChange>;
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
