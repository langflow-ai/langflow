import { ReactFlowInstance } from "reactflow";
import { tweakType } from "../components";
import { FlowType, NodeType } from "../flow";

export type FlowPoolType = {
  //TODO improve the flowPool type
  [key: string]: Array<any>;
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
  checkInputandOutput: (flow: FlowType) => boolean;
  getInputTypes: (flow: FlowType) => string[];
  getOutputTypes: (flow: FlowType) => string[];
  getInputIds: (flow: FlowType) => string[];
  getOutputIds: (flow: FlowType) => string[];
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
};
