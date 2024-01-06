import { create } from "zustand";
import { FlowState } from "../types/tabs";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  currentFlowId: "",
  setCurrentFlowId: (currentFlowId: string) => {
    set((state) => ({
      currentFlowId,
      currentFlowState: state.flowsState[state.currentFlowId],
      currentFlow: state.flows.find((flow) => flow.id === currentFlowId),
    }));
  },
  flows: [],
  currentFlow: undefined,
  isLoading: true,
  setIsLoading: (isLoading: boolean) => set({ isLoading }),
  flowsState: {},
  currentFlowState: undefined,
  setCurrentFlowState: (
    flowState: FlowState | ((oldState: FlowState | undefined) => FlowState)
  ) => {
    const newFlowState =
      typeof flowState === "function"
        ? flowState(get().currentFlowState)
        : flowState;
    set((state) => ({
      flowsState: {
        ...state.flowsState,
        [state.currentFlowId]: newFlowState,
      },
      currentFlowState: newFlowState,
    }));
  },
}));

export default useFlowsManagerStore;
