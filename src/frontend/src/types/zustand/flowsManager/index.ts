import { FlowType } from "../../flow";
import { FlowState, FlowsState } from "../../tabs";

export type FlowsManagerStoreType = {
  flows: Array<FlowType>;
  currentFlow: FlowType | undefined;
  currentFlowId: string;
  isLoading: boolean;
  setIsLoading: (isLoading: boolean) => void;
  flowsState: FlowsState;
  currentFlowState: FlowState;
  setCurrentFlowState: (state: FlowState | ((oldState: FlowState) => FlowState)) => void;
};
