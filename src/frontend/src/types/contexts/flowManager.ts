import { ReactFlowInstance } from "reactflow";
import { tweakType } from "../components";
import { FlowType, NodeDataType, NodeType } from "../flow";

export type chatInputType = {
  result: string;
};

export type ChatOutputType = {
  message: string;
  is_ai: boolean;
};

export type FlowPoolObjectType = {
  timestamp: string;
  valid: boolean;
  params: any;
  data: { artifacts: any; results: any | ChatOutputType | chatInputType };
  id: string;
};

export type FlowPoolType = {
  [key: string]: Array<FlowPoolObjectType>;
};

export type FlowManagerContextType = {
  setFilterEdge: (newState) => void;
  getFilterEdge: any[];
  deleteEdge: (idx: string | Array<string>) => void;
  deleteNode: (idx: string | Array<string>) => void;
  reactFlowInstance: ReactFlowInstance | null;
  setReactFlowInstance: (newState: ReactFlowInstance) => void;
  flowPool: FlowPoolType;
  updateFlowPoolNodes: (nodes: NodeType[]) => void;
  addDataToFlowPool: (data: any, nodeId: string) => void;
  checkInputandOutput: (flow?: FlowType) => boolean;
  getInputTypes: (flow?: FlowType) => string[];
  getOutputTypes: (flow?: FlowType) => string[];
  getInputIds: (flow?: FlowType) => string[];
  getOutputIds: (flow?: FlowType) => string[];
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  downloadFlow: (
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) => void;
  setTweak: (tweak: tweakType) => tweakType | void;
  getTweak: tweakType;
  isBuilt: boolean;
  setIsBuilt: (state: boolean) => void;
  inputTypes: string[];
  outputTypes: string[];
  inputIds: string[];
  outputIds: string[];
  showPanel: boolean;
  updateNodeFlowData: (nodeId: string, newData: NodeDataType) => void;
  buildFlow: (nodeId?:string) => Promise<void>;
  setFlow: (flow: FlowType) => void;
  pasteFileOnFLow: (file?: File) => Promise<void>;
  CleanFlowPool: () => void;
  isBuilding: boolean;
  setIsBuilding: (state: boolean) => void;
};
