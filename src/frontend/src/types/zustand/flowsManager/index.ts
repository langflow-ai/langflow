import { Node, Edge, Viewport } from "reactflow";
import { FlowType } from "../../flow";
import { FlowState, FlowsState } from "../../tabs";

export type FlowsManagerStoreType = {
  flows: Array<FlowType>;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  setCurrentFlowId: (currentFlowId: string) => void;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  flowsState: FlowsState;
  currentFlowState: FlowState | undefined;
  setCurrentFlowState: (state: FlowState | ((oldState: FlowState | undefined) => FlowState)) => void;
  refreshFlows: () => Promise<void>;
  saveFlow: (flow: FlowType, silent?: boolean) => Promise<void>;
  autoSaveCurrentFlow: (nodes: Node[], edges: Edge[], viewport: Viewport) => void;
};
