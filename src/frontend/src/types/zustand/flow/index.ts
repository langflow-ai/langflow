import {
  Connection,
  Edge,
  Node,
  OnEdgesChange,
  OnNodesChange,
  ReactFlowInstance,
  Viewport,
} from "reactflow";
import { BuildStatus } from "../../../constants/enums";
import { FlowState } from "../../tabs";

export type chatInputType = {
  result: string;
};

export type ChatOutputType = {
  message: string;
  sender: string;
  sender_name: string;
  stream_url?: string;
};

export type FlowPoolObjectType = {
  timestamp: string;
  valid: boolean;
  params: any;
  data: { artifacts: any | ChatOutputType | chatInputType; results: any | ChatOutputType | chatInputType };
  duration?: string;
  progress?: number;
  id: string;
  buildId: string;
};

export type FlowPoolType = {
  [key: string]: Array<FlowPoolObjectType>;
};

export type FlowStoreType = {
  flowPool: FlowPoolType;
  inputs: Array<{ type: string; id: string }>;
  outputs: Array<{ type: string; id: string }>;
  hasIO: boolean;
  setFlowPool: (flowPool: FlowPoolType) => void;
  addDataToFlowPool: (data: FlowPoolObjectType, nodeId: string) => void;
  CleanFlowPool: () => void;
  isBuilding: boolean;
  isPending: boolean;
  setIsBuilding: (isBuilding: boolean) => void;
  setPending: (isPending: boolean) => void;
  resetFlow: (flow: {
    nodes: Node[];
    edges: Edge[];
    viewport: Viewport;
  }) => void;
  reactFlowInstance: ReactFlowInstance | null;
  setReactFlowInstance: (newState: ReactFlowInstance) => void;
  flowState: FlowState | undefined;
  setFlowState: (
    state:
      | FlowState
      | undefined
      | ((oldState: FlowState | undefined) => FlowState)
  ) => void;
  nodes: Node[];
  edges: Edge[];
  onNodesChange: OnNodesChange;
  onEdgesChange: OnEdgesChange;
  setNodes: (update: Node[] | ((oldState: Node[]) => Node[])) => void;
  setEdges: (update: Edge[] | ((oldState: Edge[]) => Edge[])) => void;
  setNode: (id: string, update: Node | ((oldState: Node) => Node)) => void;
  getNode: (id: string) => Node | undefined;
  deleteNode: (nodeId: string | Array<string>) => void;
  deleteEdge: (edgeId: string | Array<string>) => void;
  paste: (
    selection: { nodes: any; edges: any },
    position: { x: number; y: number; paneX?: number; paneY?: number }
  ) => void;
  lastCopiedSelection: { nodes: any; edges: any } | null;
  setLastCopiedSelection: (
    newSelection: { nodes: any; edges: any } | null,
    isCrop?: boolean
  ) => void;
  cleanFlow: () => void;
  setFilterEdge: (newState) => void;
  getFilterEdge: any[];
  onConnect: (connection: Connection) => void;
  unselectAll: () => void;
  buildFlow: (nodeId?: string) => Promise<void>;
  getFlow: () => { nodes: Node[]; edges: Edge[]; viewport: Viewport };
  updateVerticesBuild: (vertices: string[]) => void;
  removeFromVerticesBuild: (vertices: string[]) => void;
  verticesBuild: string[];
  updateBuildStatus: (nodeId: string[], status: BuildStatus) => void;
  revertBuiltStatusFromBuilding: () => void;
  flowBuildStatus: { [key: string]: BuildStatus };
  updateFlowPool: (nodeId:string, data:FlowPoolObjectType | ChatOutputType | chatInputType,buildId?:string) => void;
};
