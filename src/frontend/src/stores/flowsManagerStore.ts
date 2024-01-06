import { create } from "zustand";
import { FlowsManagerStoreType } from "../types/zustand/flowsManager";
import { FlowState } from "../types/tabs";

const useFlowsManagerStore = create<FlowsManagerStoreType>((set, get) => ({
  currentFlowId: "",
  setCurrentFlowId: (currentFlowId: string) => {
    set({ currentFlowId, currentFlow: get().flows.find((flow) => flow.id === currentFlowId) });
},
  flows: [],
  currentFlow: undefined,
  isLoading: true,
  setIsLoading: (isLoading: boolean) => set({ isLoading }),
  flowsState: {},
  currentFlowState: undefined,
  setCurrentFlowState: (flowState: FlowState | ((oldState: FlowState | undefined) => FlowState)) => {
    const newFlowState = typeof flowState === "function" ? flowState(get().currentFlowState) : flowState;
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
