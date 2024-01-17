import { ReactFlowInstance } from "reactflow";
import { tweakType } from "../../components";
import { FlowType, NodeDataType, NodeType } from "../../flow";

export type chatInputType = {
  result: string;
};

export type ChatOutputType = {
  message: string;
  sender: string;
  sender_name: string;
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

export type flowIOStoreType = {
  flowPool: FlowPoolType;
  getFilterEdge: any[];
  isBuilt: boolean;
  inputTypes: string[];
  outputTypes: string[];
  inputIds: string[];
  outputIds: string[];
  isBuilding: boolean;
  setFlowPool: (flowPool: FlowPoolType) => void;
  setIsBuilding: (state: boolean) => void;
  setIsBuilt: (state: boolean) => void;
  setOutputTypes: (outputTypes: string[]) => void;
  setInputTypes: (inputTypes: string[]) => void;
  setInputIds: (inputIds: string[]) => void;
  setOutputIds: (outputIds: string[]) => void;
  setFilterEdge: (newState) => void;
  updateFlowPoolNodes: (nodes: NodeType[]) => void;
  addDataToFlowPool: (data: any, nodeId: string) => void;
  CleanFlowPool: () => void;
  updateNodeFlowData: (nodeId: string, newData: NodeDataType) => void;
  checkInputandOutput: (flow?: FlowType) => boolean;
  getInputTypes: (flow?: FlowType) => string[];
  getOutputTypes: (flow?: FlowType) => string[];
  getInputIds: (flow?: FlowType) => string[];
  getOutputIds: (flow?: FlowType) => string[];
  pasteFileOnFLow: (file?: File) => Promise<void>;
  downloadFlow: (
    flow: FlowType,
    flowName: string,
    flowDescription?: string
  ) => void;

  /* buildFlow: (nodeId?:string) => Promise<void>; */
};