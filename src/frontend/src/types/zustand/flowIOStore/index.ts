import { FlowType, NodeType } from "../../flow";

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
  setOutputTypes: (outputTypes: string[]) => void;
  setInputTypes: (inputTypes: string[]) => void;
  setInputIds: (inputIds: string[]) => void;
  setOutputIds: (outputIds: string[]) => void;
  updateFlowPoolNodes: (nodes: NodeType[]) => void;
  checkInputandOutput: (flow?: FlowType) => boolean;
  getInputTypes: (flow?: FlowType) => string[];
  getOutputTypes: (flow?: FlowType) => string[];
  getInputIds: (flow?: FlowType) => string[];
  getOutputIds: (flow?: FlowType) => string[];
};
